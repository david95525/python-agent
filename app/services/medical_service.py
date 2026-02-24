import os
import re
from typing import List, Dict, Annotated, TypedDict, Literal
import operator
import json
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.services.base import BaseAgent
from app.services.tools.system_tools import load_specialized_skill
from app.services.tools.medical_tools import (
    search_device_manual,
    get_user_health_data,
    plot_health_chart,
)
from app.schemas.agent import ChartParams
from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


# 定義 Graph 狀態
class AgentState(TypedDict):
    user_id: str
    input_message: str
    messages: Annotated[List[BaseMessage], operator.add]  # 累加對話歷史
    intent: Literal["device", "health", "general", "visualizer"]  # 路由意圖
    is_emergency: bool  # 新增：用於判斷是否觸發緊急狀態
    context_data: str  # 工具抓取的原始數據
    final_response: str  # 最終產出的回覆


class MedicalAgentService(BaseAgent):

    def __init__(self):
        super().__init__("MedicalService")
        # 載入註冊表 (Registry)
        self.skills_registry = self._load_registry()
        # 構建生產線 (Graph)
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()

        # 簡單記憶體
        self.chat_history_map: Dict[str, List[BaseMessage]] = {}

    def _load_registry(self) -> dict:
        """載入技能地圖"""
        path = os.path.join("skills", "registry.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(
                    f"[System] 技能註冊表載入成功，共 {len(data.get('skills', []))}個專業模組"
                )
                return data
        except Exception as e:
            logger.error(f"[System] 無法載入註冊表，請檢查路徑或格式: {e}")
            return {"skills": []}

    def _get_manifest_for_prompt(self) -> str:
        """將註冊表轉換為 Router 看得懂的文字"""
        manifest = []
        for skill in self.skills_registry.get("skills", []):
            manifest.append(f"- '{skill['id']}': {skill['description']}")
        manifest.append("- 'general': 處理日常寒暄、心情分享或非上述專業領域的問題。")
        return "\n".join(manifest)

    def _build_workflow(self):
        graph = StateGraph(AgentState)

        # 定義節點 (保持不變)
        graph.add_node("router", self.node_router)
        graph.add_node("device_expert", self.node_device_expert)
        graph.add_node("health_analyst", self.node_health_analyst)
        graph.add_node("emergency_advice", self.node_emergency_advice)
        graph.add_node("general_assistant", self.node_general_assistant)
        graph.add_node("visualizer", self.node_visualizer)

        graph.add_edge(START, "router")

        # 根據 router 的意圖決定去向
        graph.add_conditional_edges(
            "router",
            lambda state: state["intent"],
            {
                "device_expert": "device_expert",
                "health_analyst": "health_analyst",
                "visualizer": "visualizer",
                "general": "general_assistant",
            },
        )

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

    async def node_router(self, state: AgentState):
        """意圖路由：加入上下文參考，防止簡短回覆被誤判"""
        manifest = self._get_manifest_for_prompt()
        # 取最後一則 AI 的訊息，用以判斷上下文
        last_ai_message = ""
        if state.get("messages"):
            for m in reversed(state["messages"]):
                if isinstance(m, AIMessage):
                    last_ai_message = m.content
                    break
        # [第一層保險] 硬編碼規則：如果 AI 剛問完要不要畫圖，且用戶說「好」
        confirm_keywords = ["好", "要", "畫", "ok", "yes", "確認", "畫吧", "顯示"]
        is_asking_to_plot = "繪製趨勢分析圖表嗎" in last_ai_message
        user_input_clean = state["input_message"].strip().lower()

        if is_asking_to_plot and any(k in user_input_clean for k in confirm_keywords):
            logger.info("[Router Decision] 觸發上下文攔截規則: 導向 visualizer")
            return {"intent": "visualizer"}
        # 3. [第二層保險] LLM 判斷
        prompt = (
            "你是一個專業的任務分發中心。請根據對話歷史與用戶訊息判斷意圖：\n\n"
            f"【技能清單】\n{manifest}\n"
            "- 'visualizer': 當用戶明確要求繪圖，或同意 AI 之前的繪圖建議時使用。\n\n"  # 強制加入 visualizer 說明
            f"【最後一則 AI 回覆】\n{last_ai_message}\n\n"
            f"【用戶當前訊息】\n{state['input_message']}\n\n"
            "【關鍵判定規則】\n"
            "1. 如果 AI 上一則訊息詢問了『是否繪製圖表』，且用戶回答肯定，請務必回傳 'visualizer'。\n"
            "2. 如果用戶詢問設備故障、說明書資訊，請回傳 'device_expert'。\n"
            "3. 如果用戶提供數據要求分析，請回傳 'health_analyst'。\n"
            "4. 否則回傳 'general'。\n\n"
            "【指令】僅回傳標籤名稱 ID，嚴禁任何解釋。"
        )

        res = await self.llm.ainvoke(prompt)
        intent_text = res.content.strip().lower()
        raw_intent = intent_text.replace(".", "").replace("'", "")

        # 驗證 ID 合法性 (包含手動加入的 visualizer)
        valid_ids = [s["id"] for s in self.skills_registry.get("skills", [])]
        valid_ids.extend(["visualizer", "general"])

        final_intent = "general"
        # 依照長度排序，優先匹配較長的 ID (例如 health_analyst 優於 health)
        sorted_ids = sorted(valid_ids, key=len, reverse=True)

        for vid in sorted_ids:
            if vid.lower() in raw_intent:
                final_intent = vid
                break  # <--- 只有匹配成功才跳出迴圈

        logger.info(
            f"[Router Decision] 識別意圖: {final_intent} (原始回覆: {intent_text})"
        )
        return {"intent": final_intent}

    async def node_device_expert(self, state: AgentState):
        """硬體專家節點：專注於 RAG 檢索"""
        # 動態加載Skills
        skill_content = load_specialized_skill.invoke({"skill_name": "device_expert"})
        # 執行 RAG
        raw_info = await search_device_manual.ainvoke({"query": state["input_message"]})
        logger.info(f"[RAG] 檢索完成，獲取資料長度: {len(raw_info)} 字元")
        prompt = (
            f"### 專業執行細則 ###\n{skill_content}\n\n"
            f"### 檢索到的說明書資訊 ###\n{raw_info}\n\n"
            f"請根據上述規範回答用戶：{state['input_message']}"
        )
        res = await self.llm.ainvoke(prompt)
        return {"final_response": res.content}

    async def node_health_analyst(self, state: AgentState):
        """健康分析師節點：專注於數據處理"""
        # 動態加載Skills
        skill_info = load_specialized_skill.invoke({"skill_name": "health_analyst"})
        # 調用工具獲取血壓數據
        raw_data = get_user_health_data.invoke({"user_id": state["user_id"]})

        prompt = (
            f"### 專業規範 ###\n{skill_info}\n\n"
            f"### 真實數據 ###\n{raw_data}\n\n"
            f"### 用戶當前描述 ###\n{state['input_message']}\n\n"
            "1. 請結合歷史數據與『用戶當前描述的數值』進行綜合分析。\n"
            "2. 請根據規範分析數據。若出現任何一項『異常』(BP, SpO2, Temp)，"
            "請在文末標註 [EMERGENCY]，否則標註 [NORMAL]。"
        )

        res = await self.llm.ainvoke(prompt)

        data_list = json.loads(raw_data).get("history", [])
        can_visualize = len(data_list) >= 5
        # 新增：記錄 LLM 原始判斷
        logger.debug(f"[LLM Raw] 分析師回覆原文: {res.content}")
        is_emergency = "[EMERGENCY]" in res.content
        logger.info(f"[Risk Analysis] 是否觸發緊急狀態: {is_emergency}")
        clean_content = res.content.replace("[EMERGENCY]", "").replace("[NORMAL]", "")
        if can_visualize:
            clean_content += (
                "\n\n💡 **系統偵測到數據量充足，需要我為您繪製趨勢分析圖表嗎？**"
            )
        return {
            "final_response": clean_content,
            "is_emergency": is_emergency,
            "context_data": raw_data,
        }

    async def node_emergency_advice(self, state: AgentState):
        """緊急建議節點：臨床指引模式"""
        prompt = (
            "### 臨床風險警示 ###\n"
            "當前檢測到用戶血壓數據已達臨床警戒水位。\n"
            "請提供標準化的醫學建議：\n"
            "1. 建議用戶保持平靜，靜坐 15 分鐘後重新測量。\n"
            "2. 若伴隨頭痛、胸痛等症狀，建議立即尋求專業醫療協助或撥打緊急電話。"
        )
        res = await self.llm.ainvoke(prompt)
        combined = f"{state['final_response']}\n\n--- ⚠️ 系統臨床建議 ---\n{res.content}"

        return {"final_response": combined}

    async def node_visualizer(self, state: AgentState):
        """繪圖專家節點：動態判斷指標並調用工具產出圖表"""
        # 取得數據
        raw_data = state.get("context_data")
        if not raw_data:
            raw_data = get_user_health_data.invoke({"user_id": state["user_id"]})
            logger.warning(
                f"[Visualizer] State 中無數據，已重新抓取用戶 {state['user_id']} 數據"
            )
        # 取得用戶當前的需求
        user_intent = state["input_message"]

        # 使用 with_structured_output 確保 LLM 回傳的是 ChartParams 物件而非字串
        structured_llm = self.llm.with_structured_output(ChartParams)
        # 升級指令：讓 LLM 決定要畫什麼指標
        # 注意：這裡我們傳入 raw_data 的範例，讓 LLM 知道有哪些欄位可用
        data_sample = raw_data[:500]  # 擷取部分數據供 LLM 參考
        visualizer_prompt = (
            "你是一位資深的『數據視覺化專家』。\n"
            f"【用戶當前需求】：{user_intent}\n\n"  # 告訴 AI 用戶要看什麼
            f"【數據樣本內容】：{data_sample}\n\n"
            "【決策準則】：\n"
            "1. 指標精選：請嚴格根據『用戶當前需求』決定繪製的 columns。\n"
            "   - 若用戶說『只要看收縮壓』，columns 僅能包含 ['sys']。\n"
            "   - 若用戶未指定，則根據數據常規 (如: ['sys', 'dia']) 繪製。\n"
            "2. 類型挑選：趨勢用 'line'，對比用 'bar'。\n"
            "3. 標題與單位：標題需專業且對應指標，單位需正確。"
        )

        # 獲取 LLM 決策
        params: ChartParams = await structured_llm.ainvoke(visualizer_prompt)
        # 執行繪圖工具 (傳入動態參數)
        chart_base64 = plot_health_chart.invoke(
            {
                "data": raw_data,
                "title": params.title,
                "chart_type": params.chart_type,
                "columns": params.columns,
                "labels": params.labels,
                "unit": params.unit,
            }
        )

        # 封裝回傳
        chart_type_zh = {"line": "折線", "bar": "長條", "scatter": "散佈"}.get(
            params.chart_type, "趨勢"
        )
        final_text = (
            f"**已根據您的要求生成{chart_type_zh}圖表**：\n"
            f"分析指標：{', '.join(params.labels)}\n\n"
            f"![Health Chart]({chart_base64})"
        )

        return {"final_response": final_text}

    async def node_general_assistant(self, state: AgentState):
        """通用節點：處理範疇外問題"""
        res = await self.llm.ainvoke(
            f"你是一位禮貌的助手，請告知用戶你專注於健康數據分析或設備說明，無法回答以下問題：{state['input_message']}"
        )
        logger.info(
            f"[Router Decision] 意圖辨識結果: {state['intent']} (原始訊息: {state['input_message']})"
        )
        return {"final_response": res.content}

    # --- API 進入點 ---
    async def handle_chat(self, user_id: str, message: str) -> str:
        # 取得歷史紀錄
        history = self.chat_history_map.get(user_id, [])
        initial_state = {
            "user_id": user_id,
            "input_message": message,
            "messages": history + [HumanMessage(content=message)],
            "context_data": "",
        }
        try:
            # 啟動 LangGraph 生產線
            config = {"configurable": {"thread_id": user_id}}
            final_state = await self.app.ainvoke(initial_state, config=config)
            final_text = final_state["final_response"]
            intent = final_state.get("intent", "general")
            mermaid_graph = self.app.get_graph().draw_mermaid()
            if final_state.get("is_emergency"):
                mermaid_graph += "\nclass emergency_advice activeEmergencyNode"
            # 格式化輸出（加上追蹤資訊，方便研究分析）
            logger.info(
                f"\n\n-Agent 路由追蹤-\n意圖：{final_state.get('intent')}\n節點路徑：Router -> {final_state.get('intent')}_expert"
            )
            # 更新記憶體
            self._update_history(user_id, message, final_text)
            # 整理回傳結構
            response_data = {
                "text": final_text,
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

    def _update_history(self, user_id: str, user_msg: str, ai_msg: str):
        history = self.chat_history_map.get(user_id, [])
        # 處理 AI 訊息：如果包含巨大的 Base64 圖片，將其替換為佔位符
        cleaned_ai_msg = re.sub(
            r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "[圖表數據已存檔]", ai_msg
        )
        history.append(HumanMessage(content=user_msg))
        history.append(AIMessage(content=cleaned_ai_msg))
        # 保持最近 10 則對話 (5 輪對話)
        self.chat_history_map[user_id] = history[-10:]
        logger.info(
            f"[Memory] User: {user_id} | 歷史訊息數: {len(self.chat_history_map[user_id])} | "
            f"AI 回覆摘要: {cleaned_ai_msg[:50].replace('\n', ' ')}..."
        )


def save_graph_image(agent_service):
    try:
        # 取得編譯後的圖結構，並轉換為 Mermaid 格式的 PNG
        graph_image = agent_service.app.get_graph().draw_mermaid_png()

        with open("agent_workflow.png", "wb") as f:
            f.write(graph_image)
        logger.info("流程圖已成功儲存為 agent_workflow.png")
    except Exception as e:
        logger.error(f"無法產生圖片，請確保安裝了必要套件: {e}")
