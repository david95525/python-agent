from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from langchain_core.messages import AIMessage
from app.services.medical.state import AgentState
from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


class RouterOutput(BaseModel):
    """意圖路由與日期解析的統一輸出結構"""
    intent: Literal["device_expert", "health_analyst", "health_query",
                    "visualizer", "general"] = Field(description="用戶的主要意圖 ID")
    query_start: Optional[str] = Field(
        default=None, description="解析出的查詢起始日期，格式為 YYYY-MM-DD")
    query_end: Optional[str] = Field(
        default=None, description="解析出的查詢結束日期，格式為 YYYY-MM-DD")
    reasoning: str = Field(description="判定意圖與日期的簡短理由")


class RouterNode:

    def __init__(self, llm, manifest: str, valid_ids: list):
        self.llm = llm
        self.manifest = manifest
        self.valid_ids = valid_ids

    async def node_router(self, state: AgentState):
        """統一意圖路由：合併意圖判定與日期解析，並引入意圖慣性"""
        user_input = state["input_message"].strip().lower()
        current_date = datetime.now().strftime("%Y-%m-%d")

        # 1. 安全性攔截：隱私與越權存取 (Hard-coded Guardrail)
        privacy_keywords = ["別人的", "上一個測試員", "其他人的", "他的血壓", "誰的紀錄"]
        if any(k in user_input for k in privacy_keywords):
            logger.warning(f"[Security] 偵測到潛在隱私存取請求: {user_input}")
            return {"intent": "general"}

        # 2. 硬編碼攔截邏輯：繪圖確認
        last_ai_message = ""
        if state.get("messages"):
            for m in reversed(state["messages"]):
                if isinstance(m, AIMessage):
                    last_ai_message = m.content
                    break

        confirm_keywords = ["好", "要", "畫", "ok", "yes", "確認", "畫吧", "顯示", "可以"]
        is_asking_to_plot = "繪製趨勢分析圖表嗎" in last_ai_message
        if is_asking_to_plot and any(k in user_input
                                     for k in confirm_keywords):
            return {"intent": "visualizer"}

        # 3. LLM 統一判斷邏輯 (Structured Output)
        last_intent = state.get("last_intent", "general")
        structured_llm = self.llm.with_structured_output(RouterOutput)

        prompt = (
            f"今天是 {current_date}。\n"
            "你是一個專業的任務分發與實體提取中心。請根據對話歷史判斷意圖並提取日期範圍：\n\n"
            f"【當前技能清單】\n{self.manifest}\n\n"
            f"【上一回合意圖】：{last_intent}\n"
            f"【用戶訊息】：{state['input_message']}\n\n"
            "【判定意圖類別（ID）說明】：\n"
            "1. 'device_expert': 設備硬體、故障碼、設定問題。\n"
            "2. 'health_query': 純數據查詢。特徵是沒有詢問『為什麼』或評估。例如：『查紀錄』、『列出數據』。\n"
            "3. 'health_analyst': 涉及評估與分析。例如：『我這樣正常嗎』、『幫我分析』、『最近血壓為什麼高』。\n"
            "4. 'visualizer': 要求畫圖或調整圖表。\n"
            "5. 'general': 閒聊、問候、詢問他人隱私、或是無法理解的亂碼。\n\n"
            "【意圖慣性原則】：\n"
            "若用戶輸入較為簡短且具備延續性（如：『那昨天呢？』、『那前天呢？』），請優先延續『上一回合意圖』。\n\n"
            "【日期提取規範】：\n"
            "將口語（如：『上週』、『這三天』）轉化為具體日期。若未提及則保持 null。")

        try:
            res: RouterOutput = await structured_llm.ainvoke(prompt)
            final_intent = res.intent
            logger.info(
                f"[Router Decision] 識別意圖: {final_intent}, 日期: {res.query_start} ~ {res.query_end}"
            )

            return {
                "intent": final_intent,
                "last_intent": final_intent,
                "query_start": res.query_start,
                "query_end": res.query_end
            }
        except Exception as e:
            logger.error(f"[Router Error] LLM 呼叫失敗: {e}")
            return {"intent": "general"}
