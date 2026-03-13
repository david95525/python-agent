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
                k in state["input_message"].strip().lower()
                for k in confirm_keywords):
            return {"intent": "visualizer"}

        # 3. LLM 判斷邏輯 (第二層保險)
        last_intent = state.get("intent", "general")

        prompt = (
            "你是一個專業的任務分發中心。請根據對話歷史判斷意圖：\n\n"
            f"【當前技能清單】\n{self.manifest}\n\n"
            f"【上一回合意圖】：{last_intent}\n"
            f"【用戶訊息】：{state['input_message']}\n\n"
            "【判定意圖類別（ID）說明】：\n"
            "1. **'device_expert'**: 詢問設備操作、故障、設定、代碼等硬體問題。\n"
            "2. **'health_query'**: 單純的數據查詢。例如：『查去年紀錄』、『列出上週血壓』、『昨天測了幾次』。特徵是沒有詢問『為什麼』或『好不好』。\n"
            "3. **'health_analyst'**: 涉及健康評估與分析。例如：『我這樣正常嗎』、『最近血壓為什麼高』、『幫我分析趨勢』、『給我健康建議』。\n"
            "4. **'visualizer'**: 要求畫圖、調整圖表、或同意 AI 的繪圖建議。\n"
            "5. **'general'**: 一般打招呼或無法歸類的閒聊。\n\n"
            "【決策準則】：\n"
            "- 如果用戶同時查詢資料且要求分析（如：『查上週紀錄並分析』），優先判斷為 'health_analyst'。\n"
            "- 如果只是問『那去年呢？』且上一次是查詢，判斷為 'health_query'。\n\n"
            "【指令】僅回傳 ID，嚴禁解釋。")

        res = await self.llm.ainvoke(prompt)
        raw_intent = res.content.strip().lower().replace(".",
                                                         "").replace("'", "")

        # 4. ID 匹配邏輯
        final_intent = "general"
        sorted_ids = sorted(self.valid_ids, key=len, reverse=True)
        for vid in sorted_ids:
            if vid.lower() in raw_intent:
                final_intent = vid
                break

        logger.info(f"[Router Decision] 識別意圖: {final_intent}")
        return {"intent": final_intent}
