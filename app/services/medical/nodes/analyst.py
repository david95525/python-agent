import re
import json
from datetime import datetime
from langgraph.types import Command
from langgraph.graph import END
from app.services.tools.medical_tools import get_user_health_data
from app.services.tools.system_tools import load_specialized_skill
from app.services.medical.state import AgentState
from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


from app.utils.prompt_manager import prompt_manager

class HealthAnalystNodes:

    def __init__(self, llm):
        self.llm = llm

    async def node_check_date(self, state: AgentState):
        """
        [校驗節點] 確保使用者在查詢數據時必須提供日期。
        """
        intent = state.get("intent")
        query_start = state.get("query_start")
        input_message = state.get("input_message", "")

        # 簡單的日期提取邏輯 (例如: 2024-03-01 或 昨天/今天)
        # 這裡假設如果輸入中包含數字或特定關鍵字，就視為有提供時間資訊
        date_pattern = r"\d{4}-\d{2}-\d{2}|昨天|今天|前天|上週|這週|最近|剛才"
        has_date_info = re.search(date_pattern, input_message)
        
        # 只有在需要查詢數據的意圖下，才檢查日期
        if intent in ["health_query", "health_analyst"]:
            # 如果 Router 沒解析出日期，且訊息中也沒有明確的日期格式 (YYYY-MM-DD)
            # 我們不再信任「最近」、「這週」等模糊詞彙，因為這會導致 API 抓取過多資料
            strict_date_pattern = r"\d{4}-\d{2}-\d{2}"
            has_strict_date = re.search(strict_date_pattern, input_message)
            
            if not query_start and not has_strict_date:
                logger.info("[Validation] 缺失明確查詢日期，觸發中斷點。")
                return {
                    "final_response": "您想要查詢哪一段時間的紀錄呢？（例如：昨天、上週五，或具體日期如 2024-03-01）",
                    "is_data_missing": True,
                    "intent": "interrupt"
                }
        
        return {"is_data_missing": False}

    async def node_fetch_health_records(self, state: AgentState):
        """
        [獨立節點] 負責根據動態範圍抓取 API。
        """
        # 從 Router 拿到的時間範圍
        start = state.get("query_start")
        end = state.get("query_end")
        user_id = state.get("user_id", "default_user")
        intent = state.get("intent", "health_analyst") # 預設為分析
        
        logger.info(f"[Debug] Fetching records for intent: {intent}, range: {start} ~ {end}")

        # 呼叫工具 (此處不消耗 Gemini 配額)
        raw_response = await get_user_health_data.ainvoke({
            "user_id": user_id,
            "start_date": start,
            "end_date": end,
        })
        
        count = 0
        records = []
        try:
            data = (json.loads(raw_response)
                    if isinstance(raw_response, str) else raw_response)
            if data.get("status") == "success":
                records = data.get("history", [])
                count = data.get("total", 0)
        except Exception as e:
            logger.error(f"[Fetch Error] JSON 解析失敗: {e}")

        ui_data = {"records": records, "total": count}
        time_display = f"{start} 至 {end}" if start and end else "最近"

        # 如果是純查詢，準備好最終回覆 (由 Edge 決定是否結束)
        final_response = ""
        if intent == "health_query":
            final_response = f"已為您找到 {time_display} 期間共 {count} 筆量測紀錄。"
            if count == 0:
                final_response = f"我在 {time_display} 期間找不到您的量測紀錄。"
            
        return {
            "context_data": raw_response,
            "data_count": count,
            "is_data_missing": count == 0,
            "ui_data": ui_data,
            "final_response": final_response
        }

    async def node_health_analyst(self, state: AgentState):
        """
        醫學健康分析節點：負責獲取數據、執行 LLM 臨床分析並判斷風險等級。
        """

        raw_data = state.get("context_data")
        ui_data = state.get("ui_data")
        
        if not raw_data or state.get("data_count", 0) == 0:
            time_range = f"{state.get('query_start')} 至 {state.get('query_end')}"
            return {
                "final_response": f"我在該時段（{time_range}）找不到您的紀錄，無法進行分析。",
                "is_emergency": False,
                "context_data": raw_data,
                "is_data_missing": True
            }
            
        data_list = []
        parsed_json = {}
        try:
            # 假設 raw_data 是字串格式，先轉 JSON
            parsed_json = (json.loads(raw_data)
                           if isinstance(raw_data, str) else raw_data)
            data_list = parsed_json.get("history", [])
        except Exception as e:
            logger.error(f"解析資料失敗: {e}")
            data_list = []
            
        # 若無資料，直接中斷流程並回覆
        if not data_list:
            time_range_str = f"{state.get('query_start')} 至 {state.get('query_end')}"
            return {
                "final_response":
                f"我在系統中找不到您在該時段（{time_range_str}）的量測紀錄。\n\n💡 **建議**：您可以檢查設備是否上傳成功，或嘗試查詢其他日期範圍。",
                "is_emergency": False,
                "context_data": raw_data,  # 依然存入 state 避免重複抓取
                "is_data_missing": True
            }
        
        # 從 State 讀取已經載入好的技能指令
        skill_info = state.get("skill_instructions") or "請根據數據進行專業分析。"
        
        # 使用 PromptManager 模板
        prompt_template = prompt_manager.get_template("health_analyst")
        full_prompt = prompt_template.format_messages(
            skill_info=skill_info,
            raw_data=raw_data,
            input_message=state['input_message']
        )
        
        try:
            res = await self.llm.ainvoke(full_prompt)
            # 後續正常處理
            can_visualize = len(data_list) >= 5
            logger.debug(f"[LLM Raw] 分析師回覆原文: {res.content}")
            
            is_emergency = "[EMERGENCY]" in res.content
            clean_content = res.content.replace("[EMERGENCY]",
                                                "").replace("[NORMAL]", "")

            if can_visualize:
                clean_content += "\n\n💡 **需要我為您繪製趨勢分析圖表嗎？**"

            return {
                "final_response": clean_content,
                "analysis_summary": clean_content,
                "is_emergency": is_emergency,
                "context_data": raw_data,
                "ui_data": ui_data or {
                    "records": parsed_json.get("history", []),
                    "total": parsed_json.get("total", 0)
                },
                "is_data_missing": False
            }
            
        except Exception as e:
            logger.error(f"LLM 呼叫失敗 (Analyst): {e}")
            error_msg = "⚠️ **醫學分析功能暫時不可用**\n\n抱歉，AI 服務目前負載過高 (503) 或發生通訊異常。雖然無法進行專業臨床分析，但我已為您列出該時段的原始紀錄供您參考。"
            if "503" not in str(e) and "UNAVAILABLE" not in str(e):
                 error_msg = "⚠️ **分析服務異常**\n\n系統在執行分析時遇到一點問題。以下是您的量測數據："
            
            return {
                "final_response": error_msg,
                "is_emergency": False,
                "ui_data": ui_data or {
                    "records": parsed_json.get("history", []),
                    "total": parsed_json.get("total", 0)
                },
                "is_data_missing": False # 雖然分析失敗，但有抓到數據，所以不是資料缺失
            }
