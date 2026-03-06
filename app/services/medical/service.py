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
                    AsyncSqliteSaver.from_conn_string(self.db_path)
                )
                # 此時 self.memory 才是真正的 BaseCheckpointSaver 實例
                workflow = self._build_workflow()
                self.app = workflow.compile(checkpointer=self.memory)
                logger.info("[System] AsyncSqliteSaver 已正確啟動並編譯 Graph")

    def _build_workflow(self):
        graph = StateGraph(AgentState)
        # 準備 Router 需要的資料
        manifest = get_manifest_for_prompt(self.skills_registry)
        valid_ids = [s["id"] for s in self.skills_registry.get("skills", [])]
        valid_ids.extend(["visualizer", "general", "health_analyst"])
        # 2. 初始化拆出去的節點類別
        router_manager = RouterNode(self.llm, manifest, valid_ids)
        analyst = HealthAnalystNodes(self.llm)
        expert = ExpertNodes(self.llm)
        # 定義節點 (保持不變)
        graph.add_node("router", router_manager.node_router)
        graph.add_node("device_expert", expert.node_device_expert)
        graph.add_node("parser", analyst.node_query_parser)
        graph.add_node("health_analyst", analyst.node_health_analyst)
        graph.add_node("emergency_advice", analyst.node_emergency_advice)
        graph.add_node("general_assistant", self.node_general_assistant)
        graph.add_node("visualizer", expert.node_visualizer)

        graph.add_edge(START, "router")

        # 根據 router 的意圖決定去向
        graph.add_conditional_edges(
            "router",
            lambda state: state["intent"],
            {
                "device_expert": "device_expert",
                "health_analyst": "parser",
                "visualizer": "visualizer",
                "general": "general_assistant",
            },
        )
        graph.add_edge("parser", "health_analyst")

        def route_after_analysis(state: AgentState):
            # 優先檢查緊急狀態
            if state.get("is_emergency"):
                return "emergency"
            # 檢查使用者原始輸入是否有繪圖關鍵字
            keywords = ["圖", "畫", "chart", "plot", "visualize"]
            if any(k in state["input_message"].lower() for k in keywords):
                return "visualize"
            return "end"

        # 健康分析完後，判斷是否需要「緊急建議」
        graph.add_conditional_edges(
            "health_analyst",
            route_after_analysis,
            {"emergency": "emergency_advice", "visualize": "visualizer", "end": END},
        )
        graph.add_edge("device_expert", END)
        graph.add_edge("emergency_advice", END)
        graph.add_edge("general_assistant", END)
        graph.add_edge("visualizer", END)
        return graph

    async def node_general_assistant(self, state: AgentState):
        """通用節點：處理範疇外問題"""
        prompt = (
            "你是一位專業且溫暖的 健康顧問助手。\n"
            "【職責說明】\n"
            "1. 處理日常寒暄（如：你好、早安）。\n"
            "2. 處理心情分享（如：我今天覺得很累），給予溫暖的回應並導向健康關注。\n"
            "3. **嚴格拒絕**非醫療/健康/設備領域的專業問題（如：股票、法律、程式開發）。\n\n"
            "【拒絕範例】\n"
            "『抱歉，我目前的專業能力專注於 Microlife 設備支援與健康數據分析，無法提供關於 [用戶問題領域] 的建議。』\n\n"
            f"【用戶當前訊息】：{state['input_message']}\n"
            "請以專業、簡潔且具備同理心的口吻回覆。"
        )
        res = await self.llm.ainvoke(prompt)
        logger.info(f"[General Assistant] 處理完畢。意圖: {state.get('intent', 'N/A')}")
        return {"final_response": res.content}

    # --- API 進入點 ---
    async def handle_chat(self, user_id: str, message: str) -> str:
        if self.app is None:
            await self.initialize()
        # 取得歷史紀錄
        config = {"configurable": {"thread_id": user_id}}
        # initial_state 只需要傳入「增量」的東西
        initial_state = {
            "user_id": user_id,
            "input_message": message,
            "messages": [HumanMessage(content=message)],  # operator.add 會自動累加
        }
        try:
            # 啟動 LangGraph 生產線
            final_state = await self.app.ainvoke(initial_state, config=config)
            intent = final_state.get("intent", "general")
            mermaid_graph = self.app.get_graph().draw_mermaid()
            if final_state.get("is_emergency"):
                mermaid_graph += "\nclass emergency_advice activeEmergencyNode"
            # 格式化輸出（加上追蹤資訊，方便研究分析）
            logger.info(
                f"\n\n-Agent 路由追蹤-\n意圖：{final_state.get('intent')}\n節點路徑：Router -> {final_state.get('intent')}_expert"
            )
            # 整理回傳結構
            response_data = {
                "text": final_state["final_response"],
                "graph": mermaid_graph,
                "intent": intent,
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
