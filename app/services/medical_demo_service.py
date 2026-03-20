# app/services/medical_demo_service.py
from datetime import datetime, timedelta
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.services.base import BaseAgent
from app.utils.logger import setup_logger
from app.services.tools.medical_tools import get_user_health_data

from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

logger = setup_logger("MedicalDemoService")


class AnalysisResponse(BaseModel):
    summary: str = Field(description="直接回答用戶的問題。例如：'您共有 3 筆血壓超過 130。'")
    data_list: Optional[List[dict]] = Field(
        default=[], description="符合用戶條件的數據。若用戶問『超過130的』，這裡就只放超過130的數據。")
    statistics: Optional[dict] = Field(default=None,
                                       description="統計數據。若用戶沒問統計，可為空。")
    highlights: Optional[dict] = Field(
        default=None, description="存放關鍵數值，例如 {'符合次數': 3, '平均收縮壓': 135}")
    mode: str = Field(
        description="回覆模式：'list' (清單), 'stats' (統計), 'highlights' (特定分析)")


class DateRange(BaseModel):
    start_date: Optional[str] = Field(description="查詢起始日期，格式為 YYYY-MM-DD")
    end_date: Optional[str] = Field(description="查詢結束日期，格式為 YYYY-MM-DD")


class MedicalDemoService(BaseAgent):

    def __init__(self):
        super().__init__("MedicalDemoService")
        # 設定資料庫路徑 (SQLite)
        self.db_path = "sqlite:///medical_chat_history.db"

    def _get_chat_history(self, session_id: str):
        """獲取該 Session 的歷史紀錄對象"""
        return SQLChatMessageHistory(session_id=session_id,
                                     connection_string=self.db_path)

    async def run_demo_chat(self, user_id: str, message: str) -> str:
        logger.info(f"[Demo Service] 處理用戶 {user_id} 的請求: {message}")

        # 使用 user_id 作為 session_id (也可以根據需求傳入不同的 session_id)
        history = self._get_chat_history(user_id)

        try:
            # 解析日期 (這部分通常不需要記憶，維持原樣)
            date_analyzer = self.llm.with_structured_output(DateRange)
            today_str = datetime.now().strftime("%Y-%m-%d")
            one_year_ago = (datetime.now() -
                            timedelta(days=365)).strftime("%Y-%m-%d")

            date_prompt = f"今天日期 {today_str}。請解析問題中的時間範圍，無指定則預設為 {one_year_ago} 到 {today_str}。問題：{message}"
            parsed_dates = await date_analyzer.ainvoke(date_prompt)

            # 獲取數據
            health_data_json = await get_user_health_data.ainvoke({
                "user_id":
                user_id,
                "start_date":
                parsed_dates.start_date,
                "end_date":
                parsed_dates.end_date,
            })

            # 結構化分析 (加入記憶)
            structured_llm = self.llm.with_structured_output(AnalysisResponse)

            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一個生理數據助理。你的任務是「精準理解問題」並「過濾/分析數據」。
                 注意：請參考之前的對話紀錄（如果有），以理解「其中」、「那些」等指代內容。
                 
                 【處理邏輯】
                 1. **過濾意圖**：若用戶問特定範圍，請在 `data_list` 僅提供符合條件的數據。
                 2. **計數意圖**：若用戶問「幾筆」，請在 `summary` 回答數字，並將關鍵統計放入 `highlights`。
                 3. **模糊詢問**：評估趨勢並給予穩定性建議（禁止醫療建議）。
                 
                 【回覆原則】
                 - **禁止醫療建議**：不可建議就醫或吃藥。
                 - **只說實話**：僅能使用提供的數據。
                 - **簡潔**：`summary` 保持在兩句話以內。"""),

                # --- 這裡插入歷史紀錄 ---
                MessagesPlaceholder(variable_name="chat_history"),
                ("human",
                 "【查詢範圍】: {range}\n【用戶健康數據】: {health_data}\n\n【用戶問題】: {user_message}"
                 )
            ])

            chain = prompt | structured_llm

            # 讀取最近的歷史訊息 (例如最近 10 條)
            current_history = history.messages[-10:]

            # 執行
            result_obj = await chain.ainvoke({
                "chat_history": current_history,
                "range":
                f"{parsed_dates.start_date} 至 {parsed_dates.end_date}",
                "health_data": health_data_json,
                "user_message": message,
            })

            # 重要：將本次對話存入資料庫
            history.add_user_message(message)
            # 因為 result_obj 是物件，我們存入其 summary 作為 AI 的回覆記憶
            history.add_ai_message(result_obj.summary)

            return result_obj.model_dump_json()

        except Exception as e:
            logger.error(f"[Demo Service Error] 執行失敗: {str(e)}", exc_info=True)
            return '{"summary": "抱歉，分析數據時發生錯誤。", "mode": "error"}'
