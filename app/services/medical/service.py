import asyncio
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command, interrupt
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
        self.skills_registry = load_skills_registry()
        self.db_path = "./state_db.sqlite"
        self.memory = None
        self.app = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()
        self._init_lock = asyncio.Lock()

    async def initialize(self):
        async with self._init_lock:
            if self.memory is None:
                self.memory = await self._exit_stack.enter_async_context(
                    AsyncSqliteSaver.from_conn_string(self.db_path))
                workflow = self._build_workflow()
                self.app = workflow.compile(checkpointer=self.memory)
                logger.info("[System] LangGraph App 已編譯並啟用 Checkpointer")

    def _build_workflow(self):
        graph = StateGraph(AgentState)
        manifest = get_manifest_for_prompt(self.skills_registry)
        valid_ids = [s["id"] for s in self.skills_registry.get("skills", [])]
        valid_ids.extend(
            ["visualizer", "general", "health_analyst", "health_query"])

        router_manager = RouterNode(self.llm, manifest, valid_ids)
        analyst = HealthAnalystNodes(self.llm)
        expert = ExpertNodes(self.llm)

        # 定義節點
        graph.add_node("router", router_manager.node_router)
        graph.add_node("check_date",
                       self.node_check_date_wrapper(analyst.node_check_date))
        graph.add_node("device_expert", expert.node_device_expert)
        graph.add_node("fetch_records", analyst.node_fetch_health_records)
        graph.add_node("health_analyst", analyst.node_health_analyst)
        graph.add_node("general_assistant", self.node_general_assistant)
        graph.add_node("visualizer", expert.node_visualizer)

        # --- 定義邊與路由邏輯 ---
        
        graph.add_edge(START, "router")

        # 1. Router 的分支路由 (補上 path_map 讓 Mermaid 畫出連線)
        def router_branch(state: AgentState):
            intent = state.get("intent")
            if intent == "device_expert":
                return "device_expert"
            elif intent in ["health_analyst", "health_query"]:
                return "check_date"
            elif intent == "visualizer":
                return "visualizer"
            else:
                return "general_assistant"

        graph.add_conditional_edges(
            "router", 
            router_branch,
            {
                "device_expert": "device_expert",
                "check_date": "check_date",
                "visualizer": "visualizer",
                "general_assistant": "general_assistant"
            }
        )

        # 2. 數據查詢路徑
        graph.add_edge("check_date", "fetch_records")

        # 3. Fetch Records 後的分流 (補上 path_map)
        def fetch_branch(state: AgentState):
            if state.get("intent") == "health_query":
                return "__end__" # LangGraph 內部使用 __end__ 表示結束節點
            return "health_analyst"

        graph.add_conditional_edges(
            "fetch_records", 
            fetch_branch,
            {
                "health_analyst": "health_analyst",
                "__end__": END
            }
        )

        # 4. 其他終點
        graph.add_edge("health_analyst", END)
        graph.add_edge("device_expert", END)
        graph.add_edge("general_assistant", END)
        graph.add_edge("visualizer", END)

        return graph

    def node_check_date_wrapper(self, original_node):
        """包裝原有的 check_date 節點以支援 interrupt"""

        async def wrapper(state: AgentState):
            result = await original_node(state)
            # 實作 Human-in-the-loop 中斷：如果缺少日期，使用 interrupt 暫停
            if result.get("is_data_missing"):
                logger.info("[Interrupt] 缺少日期資訊，進入等待狀態...")
                
                question = result.get("final_response") or "請提供您想查詢的日期範圍（例如：昨天、上週、或特定日期）。"
                
                user_input = interrupt({
                    "question": question,
                    "missing_field": "date_range"
                })
                # 恢復執行後，強行跳轉回 router 重新解析
                return Command(
                    goto="router",
                    update={
                        "input_message": f"{state['input_message']} (補充資訊: {user_input})",
                        "is_data_missing": False,
                        "query_start": None,
                        "query_end": None
                    }
                )
            return result

        return wrapper

    async def node_general_assistant(self, state: AgentState):
        prompt_template = prompt_manager.get_template("general_assistant")
        full_prompt = prompt_template.format_messages(
            input_message=state['input_message'])
        res = await self.llm.ainvoke(full_prompt)
        return {"final_response": res.content}

    async def handle_chat(self, user_id: str, message: str):
        """ 串流處理邏輯保持不變 """
        if self.app is None:
            await self.initialize()

        config = {"configurable": {"thread_id": user_id}}
        state = await self.app.aget_state(config)

        if state.next:
            logger.info(f"[Resume] 恢復執行 Thread: {user_id}")
            input_data = Command(resume=message)
        else:
            input_data = {
                "user_id": user_id,
                "input_message": message,
                "messages": [HumanMessage(content=message)],
            }

        async for event in self.app.astream_events(input_data, config, version="v2"):
            kind = event["event"]
            node_name = event.get("metadata", {}).get("langgraph_node", "")

            if kind == "on_chat_model_stream":
                if node_name == "router":
                    continue
                content = event["data"]["chunk"].content
                if content:
                    yield {"type": "stream", "content": content}

            elif kind == "on_chain_start":
                name = event.get("name", "")
                if name == "router":
                    yield {"type": "status", "content": "正在分析您的意圖..."}
                elif name == "fetch_records":
                    yield {"type": "status", "content": "正在查詢健康數據庫..."}
                elif name == "health_analyst":
                    yield {"type": "status", "content": "正在進行醫學數據分析..."}
                
                mermaid_graph = self.app.get_graph().draw_mermaid()
                yield {"type": "graph", "content": mermaid_graph, "node": name}

            elif kind == "on_chain_end" and event["name"] == "LangGraph":
                final_output = event["data"]["output"]
                mermaid_graph = self.app.get_graph().draw_mermaid()
                
                if isinstance(final_output, dict) and "final_response" in final_output:
                    compat_data = {
                        "text": final_output.get("final_response", ""),
                        "graph": mermaid_graph,
                        "intent": final_output.get("intent", "general"),
                        "is_emergency": final_output.get("is_emergency", False),
                        "ui_data": final_output.get("ui_data")
                    }
                    yield {"type": "final", "data": compat_data}
                else:
                    yield {"type": "graph", "content": mermaid_graph}

        new_state = await self.app.aget_state(config)
        if new_state.next and new_state.tasks:
            for task in new_state.tasks:
                if task.interrupts:
                    for intr in task.interrupts:
                        yield {
                            "type": "interrupt",
                            "content": intr.value.get("question") if isinstance(intr.value, dict) else str(intr.value),
                            "missing_field": intr.value.get("missing_field") if isinstance(intr.value, dict) else None
                        }

    async def close(self):
        await self._exit_stack.aclose()
        logger.info("[System] MedicalAgentService 資源已回收")
