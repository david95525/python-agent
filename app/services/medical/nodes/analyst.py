import re
import json
from datetime import datetime  # <--- 記得補上這個，否則 node_query_parser 會報錯
from app.services.tools.medical_tools import get_user_health_data
from app.services.tools.system_tools import load_specialized_skill
from app.services.medical.state import AgentState
from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


class HealthAnalystNodes:

    def __init__(self, llm):
        self.llm = llm

    async def node_query_parser(self, state: AgentState):
        """
        專門節點：分析用戶意圖，提取 API 需要的日期範圍。
        """
        logger.info(f"[Parser] 正在解析用戶請求中的時間範圍: {state['input_message']}")
        # 確保這裡的代碼縮排是 4 個空格（相對於 async def）
        current_date = datetime.now().strftime("%Y-%m-%d")
        prompt = (f"今天是 {current_date}。\n"
                  f"用戶問題：{state['input_message']}\n\n"
                  "請從問題中提取日期範圍。如果是『最近』或『沒提到時間』，請保持為 null。\n"
                  '請回傳 JSON 格式：{"start": "yyyy-mm-dd", "end": "yyyy-mm-dd"}')
        res = await self.llm.ainvoke(prompt)
        content = res.content.strip()
        # 使用正則表達式提取 JSON 部分
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        try:
            dates = json.loads(content)
            logger.info(f"[Parser Success] 解析結果: {dates}")
        except Exception as e:
            logger.error(f"[Parser Error] 依然無法解析: {content}")
            dates = {"start": None, "end": None}

        return {
            "query_start": dates.get("start"),
            "query_end": dates.get("end")
        }

    async def node_fetch_health_records(self, state: AgentState):
        """
        [獨立節點] 負責根據動態範圍抓取 API。
        """
        # 從 Parser 拿到的時間範圍
        start = state.get("query_start")
        end = state.get("query_end")

        logger.info(f"[Debug] 從 Parser 接收到的時間範圍: start={start}, end={end}")

        # 呼叫工具 (此處不消耗 Gemini 配額)
        raw_response = await get_user_health_data.ainvoke({
            "user_id":
            state["user_id"],
            "start_date":
            start,
            "end_date":
            end,
        })
        count = 0
        records = []
        # 解析並檢查是否有資料
        try:
            data = (json.loads(raw_response)
                    if isinstance(raw_response, str) else raw_response)
            if data.get("status") == "success":
                records = data.get("history", [])
                count = data.get("total", 0)
        except Exception as e:
            logger.error(f"[Fetch Error] JSON 解析失敗: {e}")
            count = 0
        # 建立 UI 數據
        ui_data = {"records": records, "total": count}

        # 建立純查詢的預設回覆
        time_display = f"{start} 至 {end}" if start and end else "最近"
        text_reply = f"已為您找到 {time_display} 期間共 {count} 筆量測紀錄。"
        return {
            "context_data":
            raw_response,
            "data_count":
            count,
            "ui_data":
            ui_data,
            "final_response":
            text_reply if state.get("intent") == "health_query" else ""
        }

    async def node_health_analyst(self, state: AgentState):
        """
        醫學健康分析節點：負責獲取數據、執行 LLM 臨床分析並判斷風險等級。
        """

        raw_data = state.get("context_data")

        data_list = []
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
            }
        # 只有有資料才去載入技能與呼叫 LLM
        skill_info = load_specialized_skill.invoke(
            {"skill_name": "health_analyst"})
        prompt = (
            f"### 專業知識庫 ###\n{skill_info}\n\n"
            f"### 待分析原始數據 ###\n{raw_data}\n\n"
            f"### 用戶指令 ###\n{state['input_message']}\n\n"
            "【強制規範】\n"
            "1. 不要列出量測清單（前端已顯示表格）。\n"
            "2. **分析原則**：聚焦於數據趨勢總結（例如：數值波動情況、平均水位）。\n"
            "3. **安全警告**：若數據含緊急血壓(≥160/100)，必須標註 [EMERGENCY]，並加上一句：『⚠️ 偵測到血壓數值過高，請立即尋求專業醫療協助或撥打急救電話。』\n"
            "4. **嚴禁建議**：禁止提供任何關於飲食、運動、情緒或生活習慣的建議（如：多喝水、少吃鹽、放鬆心情等）。")
        try:
            res = await self.llm.ainvoke(prompt)
        except Exception as e:
            logger.error(f"LLM 呼叫失敗: {e}")
            return {
                "final_response": "抱歉，目前系統分析功能暫時無法使用，請稍後再試。",
                "is_emergency": False,
            }
        # 後續處理
        can_visualize = len(data_list) >= 5

        logger.debug(f"[LLM Raw] 分析師回覆原文: {res.content}")
        ui_data = {
            "records": parsed_json.get("history", []),
            "total": parsed_json.get("total", 0)
        }
        is_emergency = "[EMERGENCY]" in res.content
        clean_content = res.content.replace("[EMERGENCY]",
                                            "").replace("[NORMAL]", "")

        if can_visualize:
            clean_content += "\n\n💡 **需要我為您繪製趨勢分析圖表嗎？**"

        return {
            "final_response": clean_content,
            "is_emergency": is_emergency,
            "context_data": raw_data,
            "ui_data": ui_data
        }
