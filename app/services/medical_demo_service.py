# app/services/medical_demo_service.py
from datetime import datetime, timedelta
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.services.base import BaseAgent
from app.utils.logger import setup_logger
from app.services.tools.medical_tools import get_user_health_data
from langchain_core.prompts import ChatPromptTemplate

logger = setup_logger("MedicalDemoService")


class AnalysisResponse(BaseModel):
    summary: str = Field(description="對數據的簡短文字總結或回答")
    data_list: Optional[List[dict]] = Field(
        description="原始數據清單，若用戶沒要求統計則提供"
    )
    statistics: Optional[dict] = Field(
        description="統計結果，如 average_sys, max_dia 等"
    )
    mode: str = Field(description="目前回覆模式：'list' 代表列表, 'stats' 代表統計分析")


class DateRange(BaseModel):
    start_date: Optional[str] = Field(description="查詢起始日期，格式為 YYYY-MM-DD")
    end_date: Optional[str] = Field(description="查詢結束日期，格式為 YYYY-MM-DD")


class MedicalDemoService(BaseAgent):
    def __init__(self):
        super().__init__("MedicalDemoService")

    async def run_demo_chat(self, user_id: str, message: str) -> str:
        logger.info(f"[Demo Service] 處理用戶 {user_id} 的請求: {message}")

        try:
            # 1. 解析日期
            date_analyzer = self.llm.with_structured_output(DateRange)
            today_str = datetime.now().strftime("%Y-%m-%d")
            one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

            date_prompt = f"今天日期 {today_str}。請解析問題中的時間範圍，無指定則預設為 {one_year_ago} 到 {today_str}。問題：{message}"
            parsed_dates = await date_analyzer.ainvoke(date_prompt)

            # 2. 獲取數據
            health_data_json = await get_user_health_data.ainvoke(
                {
                    "user_id": user_id,
                    "start_date": parsed_dates.start_date,
                    "end_date": parsed_dates.end_date,
                }
            )

            # 3. 結構化分析
            # 注意：這裡直接使用物件，不接 output_parser
            structured_llm = self.llm.with_structured_output(AnalysisResponse)

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        """你是一個生理數據助理。請根據提供的數據回答問題並輸出 JSON。
                    【規則】
                    1. 若用戶要統計，請計算平均值、最大/最小值等存入 statistics 欄位，mode 設為 'stats'。
                    2. 若用戶要清單或沒具體要求統計，請將原始數據存入 data_list，mode 設為 'list'。
                    3. summary 欄位請提供一句簡短的親切問候或數據概況。
                    4. 嚴格禁止提供醫療建議（如：建議就醫、多喝水、少吃鹽）。
                    5. 嚴格禁止回答與生理數據無關的問題。""",
                    ),
                    (
                        "human",
                        "【查詢範圍】: {range}\n【用戶健康數據】: {health_data}\n\n【用戶問題】: {user_message}",
                    ),
                ]
            )

            # 組合鏈：這裡不加 parser
            chain = prompt | structured_llm

            # 執行
            result_obj = await chain.ainvoke(
                {
                    "range": f"{parsed_dates.start_date} 至 {parsed_dates.end_date}",
                    "health_data": health_data_json,
                    "user_message": message,
                }
            )

            # 4. 回傳 JSON 字串給前端
            return result_obj.model_dump_json()

        except Exception as e:
            logger.error(f"[Demo Service Error] 執行失敗: {str(e)}", exc_info=True)
            # 為了前端解析不崩潰，出錯時也回傳符合結構的 JSON
            return '{"summary": "抱歉，分析數據時發生錯誤。", "mode": "error"}'
