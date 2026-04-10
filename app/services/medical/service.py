import asyncio
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from contextlib import AsyncExitStack

from app.services.base import BaseAgent

from app.utils.logger import setup_logger
from app.utils.registry_loader import load_skills_registry, get_manifest_for_prompt
from app.services.medical.nodes.router import RouterNode
from app.services.medical.nodes.analyst import HealthAnalystNodes
from app.services.medical.nodes.expert import ExpertNodes
from app.services.medical.state import AgentState

logger = setup_logger("AgentService")


from app.utils.prompt_manager import prompt_manager

class MedicalAgentService(BaseAgent):

    def __init__(self):
        super().__init__("MedicalService")
        # 載入註冊表 (Registry)
        self.skills_registry = load_skills_registry()
        self.db_path = "./state_db.sqlite"
        self.memory = None
        self.app = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._init_lock = asyncio.Lock()

    async def initialize(self):
        """非同步初始化 Checkpointer 與 App"""
        async with self._init_lock:
            if self.memory is None:
                # 使用 AsyncSqliteSaver
                self.memory = await self._exit_stack.enter_async_context(
                    AsyncSqliteSaver.from_conn_string(self.db_path))
                # 此時 self.memory 才是真正的 BaseCheckpointSaver 實例
                workflow = self._build_workflow()
                self.app = workflow.compile(checkpointer=self.memory)
                logger.info("[System] AsyncSqliteSaver 已正確啟動並編譯 Graph")

    def _build_workflow(self):
        graph = StateGraph(AgentState)
        # 準備 Router 需要的資料
        manifest = get_manifest_for_prompt(self.skills_registry)
        valid_ids = [s["id"] for s in self.skills_registry.get("skills", [])]
        valid_ids.extend(
            ["visualizer", "general", "health_analyst", "health_query"])

        # 2. 初始化拆出去的節點類別
        router_manager = RouterNode(self.llm, manifest, valid_ids)
        analyst = HealthAnalystNodes(self.llm)
        expert = ExpertNodes(self.llm)

        # 定義節點
        graph.add_node("router", router_manager.node_router)
        graph.add_node("check_date", analyst.node_check_date)
        graph.add_node("device_expert", expert.node_device_expert)
        graph.add_node("fetch_records", analyst.node_fetch_health_records)
        graph.add_node("health_analyst", analyst.node_health_analyst)
        graph.add_node("general_assistant", self.node_general_assistant)
        graph.add_node("visualizer", expert.node_visualizer)

        graph.add_edge(START, "router")

        # 根據 router 的意圖決定去向
        graph.add_conditional_edges(
            "router",
            lambda state: state["intent"],
            {
                "device_expert": "device_expert",
                "health_analyst": "check_date",
                "health_query": "check_date",
                "visualizer": "visualizer",
                "general": "general_assistant",
            },
        )

        def route_after_check_date(state: AgentState):
            # 如果標記為缺失資料（日期），直接結束要求輸入
            if state.get("is_data_missing"):
                return "need_info"
            return "fetch"

        graph.add_conditional_edges("check_date", route_after_check_date, {
            "need_info": END,
            "fetch": "fetch_records"
        })

        # Fetch 之後的關鍵動態路由
        def route_after_fetch(state: AgentState):
            if state.get("is_data_missing"):
                return "end_with_no_data"
            # 如果意圖是純查詢，直接結束
            if state.get("intent") == "health_query":
                return "end_with_data"
            # 否則進入分析節點
            return "analyze"

        graph.add_conditional_edges("fetch_records", route_after_fetch, {
            "analyze": "health_analyst",
            "end_with_data": END,
            "end_with_no_data": END
        })

        def route_after_analysis(state: AgentState):
            # 優先檢查緊急狀態
            if state.get("is_emergency"):
                return "emergency"
            # 檢查使用者原始輸入是否有繪圖關鍵字
            keywords = ["圖", "畫", "chart", "plot", "visualize"]
            if any(k in state["input_message"].lower() for k in keywords):
                return "visualize"
            return "end"

        # 健康分析完後，判斷是否需要繪圖
        graph.add_conditional_edges(
            "health_analyst",
            route_after_analysis,
            {
                "visualize": "visualizer",
                "emergency": END,  # 緊急情況目前直接回傳
                "end": END
            },
        )
        graph.add_edge("device_expert", END)
        graph.add_edge("general_assistant", END)
        graph.add_edge("visualizer", END)
        return graph

    async def node_general_assistant(self, state: AgentState):
        """通用節點：處理範疇外問題"""
        # 使用 PromptManager 模板
        prompt_template = prompt_manager.get_template("general_assistant")
        full_prompt = prompt_template.format_messages(
            input_message=state['input_message']
        )
        
        res = await self.llm.ainvoke(full_prompt)
        logger.info(
            f"[General Assistant] 處理完畢。意圖: {state.get('intent', 'N/A')}")
        return {"final_response": res.content}

    # --- API 進入點 ---
    async def handle_chat(self, user_id: str, message: str) -> str:
        if self.app is None:
            await self.initialize()
        
        # 加入 tags 與 metadata 方便在 LangSmith 監控與過濾
        config = {
            "configurable": {"thread_id": user_id},
            "tags": ["medical_assistant", f"user_{user_id}"],
            "metadata": {
                "source": "web_chat",
                "user_id": user_id,
                "agent_name": "MedicalAgentService"
            }
        }
        
        # 正常的起始執行
        initial_state = {
            "user_id": user_id,
            "input_message": message,
            "messages": [HumanMessage(content=message)],
        }
        
        try:
            # 啟動 LangGraph 生產線
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            intent = final_state.get("intent", "general")
            mermaid_graph = self.app.get_graph().draw_mermaid()
            
            response_data = {
                "text": final_state.get("final_response", ""),
                "graph": mermaid_graph,
                "intent": intent,
                "is_emergency": final_state.get("is_emergency", False),
                "ui_data": final_state.get("ui_data")
            }
            logger.info(f"[Response] User: {user_id}, Intent: {intent}")
            return response_data

        except Exception as e:
            logger.error(f"Graph Execution Error: {e}", exc_info=True)
            return {
                "text": "分析過程出現異常，請檢查數據或稍後再試。",
                "graph": "",
                "intent": "error",
            }

    async def close(self):
        """關閉所有由 ExitStack 管理的資源 (如資料庫連線)"""
        await self._exit_stack.aclose()
        logger.info("[System] MedicalAgentService 資源已回收")
