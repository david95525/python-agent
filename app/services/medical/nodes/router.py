from langchain_core.messages import AIMessage
from app.services.medical.state import AgentState
from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


class RouterNode:
    def __init__(self, llm, manifest: str, valid_ids: list):
        self.llm = llm
        self.manifest = manifest
        self.valid_ids = valid_ids

    async def node_router(self, state: AgentState):
        """意圖路由：負責判斷下一步去向"""
        # 1. 提取上下文
        last_ai_message = ""
        if state.get("messages"):
            for m in reversed(state["messages"]):
                if isinstance(m, AIMessage):
                    last_ai_message = m.content
                    break

        # 2. 硬編碼攔截邏輯 (第一層保險)
        confirm_keywords = ["好", "要", "畫", "ok", "yes", "確認", "畫吧", "顯示"]
        is_asking_to_plot = "繪製趨勢分析圖表嗎" in last_ai_message
        if is_asking_to_plot and any(
            k in state["input_message"].strip().lower() for k in confirm_keywords
        ):
            return {"intent": "visualizer"}

        # 3. LLM 判斷邏輯 (第二層保險)
        last_intent = state.get("intent", "general")

        prompt = (
            "你是一個專業的任務分發中心。請根據對話歷史判斷意圖：\n\n"
            f"【當前技能清單】\n{self.manifest}\n\n"
            f"【上一回合意圖】：{last_intent}\n"
            f"【用戶訊息】：{state['input_message']}\n\n"
            "【判定優先順序（由高至低）】：\n"
            "1. **明確指令偵測**：\n"
            "   - 詢問設備操作、故障、代碼 -> 'device_expert'\n"
            "   - 提供新數據、要求健康分析、詢問數值意義 -> 'health_analyst'\n"
            "   - 要求畫圖、調整圖表樣式、同意繪圖建議 -> 'visualizer'\n\n"
            "2. **上下文慣性（追問判定）**：\n"
            "   - 若訊息簡短且具指代性（如：『那去年呢？』、『平均是多少？』、『為什麼？』），請維持與『上一回合意圖』一致。\n\n"
            "3. **狀態回應**：\n"
            "   - 若 AI 剛詢問是否畫圖且用戶回答『好/要/ok』 -> 'visualizer'\n\n"
            "4. **預設行為**：\n"
            "   - 以上皆非 -> 'general'\n\n"
            "【指令】僅回傳 ID，嚴禁解釋。"
        )

        res = await self.llm.ainvoke(prompt)
        raw_intent = res.content.strip().lower().replace(".", "").replace("'", "")

        # 4. ID 匹配邏輯
        final_intent = "general"
        sorted_ids = sorted(self.valid_ids, key=len, reverse=True)
        for vid in sorted_ids:
            if vid.lower() in raw_intent:
                final_intent = vid
                break

        logger.info(f"[Router Decision] 識別意圖: {final_intent}")
        return {"intent": final_intent}
