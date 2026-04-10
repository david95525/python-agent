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


from app.utils.prompt_manager import prompt_manager
from app.services.tools.system_tools import load_specialized_skill

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

        # 從 PromptManager 獲取模板
        prompt_template = prompt_manager.get_template("router")
        full_prompt = prompt_template.format_messages(
            current_date=current_date,
            manifest=self.manifest,
            last_intent=last_intent,
            input_message=state['input_message']
        )

        try:
            res: RouterOutput = await structured_llm.ainvoke(full_prompt)
            final_intent = res.intent
            logger.info(
                f"[Router Decision] 識別意圖: {final_intent}, 日期: {res.query_start} ~ {res.query_end}"
            )

            # 動態準備 Skill 指令 (Skill Prep)
            skill_instructions = None
            if final_intent in ["health_analyst", "device_expert"]:
                skill_instructions = load_specialized_skill.invoke(
                    {"skill_name": final_intent})

            return {
                "intent": final_intent,
                "last_intent": final_intent,
                "query_start": res.query_start,
                "query_end": res.query_end,
                "skill_instructions": skill_instructions
            }
        except Exception as e:
            logger.error(f"[Router Error] LLM 呼叫失敗: {e}")
            return {"intent": "general"}
