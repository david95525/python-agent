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
        prompt = (
            f"今天是 {current_date}。\n"
            f"用戶問題：{state['input_message']}\n\n"
            "請從問題中提取日期範圍。如果是『最近』或『沒提到時間』，請保持為 null。\n"
            '請回傳 JSON 格式：{"start": "yyyy-mm-dd", "end": "yyyy-mm-dd"}'
        )
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

        return {"query_start": dates.get("start"), "query_end": dates.get("end")}

    async def node_health_analyst(self, state: AgentState):
        """
        醫學健康分析節點：負責獲取數據、執行 LLM 臨床分析並判斷風險等級。
        """
        logger.info(
            f"[Debug] 從 Parser 接收到的時間範圍: start={state.get('query_start')}, end={state.get('query_end')}"
        )
        raw_data = state.get("context_data")
        is_error_cache = raw_data and '"status": "error"' in raw_data
        logger.info(f"[Debug] 原先儲存的raw_date={raw_data}")

        if not raw_data or is_error_cache:
            logger.info(
                f"觸發 API 抓取數據 (原因: {'緩存為空' if not raw_data else '清除錯誤緩存'})"
            )
            raw_data = await get_user_health_data.ainvoke(
                {
                    "user_id": state["user_id"],
                    "start_date": state.get("query_start"),
                    "end_date": state.get("query_end"),
                }
            )
            logger.info(f"[Debug] API 回傳數據長度: {len(raw_data) if raw_data else 0}")
            logger.debug(f"[Debug] API 原始內容: {raw_data[:500]}")

        data_list = []
        try:
            # 假設 raw_data 是字串格式，先轉 JSON
            parsed_json = (
                json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            )
            data_list = parsed_json.get("history", [])
        except Exception as e:
            logger.error(f"解析資料失敗: {e}")
            data_list = []
        # 若無資料，直接中斷流程並回覆
        if not data_list:
            time_range_str = f"{state.get('query_start')} 至 {state.get('query_end')}"
            return {
                "final_response": f"我在系統中找不到您在該時段（{time_range_str}）的量測紀錄。\n\n💡 **建議**：您可以檢查設備是否上傳成功，或嘗試查詢其他日期範圍。",
                "is_emergency": False,
                "context_data": raw_data,  # 依然存入 state 避免重複抓取
            }
        # 只有有資料才去載入技能與呼叫 LLM
        skill_info = load_specialized_skill.invoke({"skill_name": "health_analyst"})
        prompt = (
            f"### 專業規範 ###\n{skill_info}\n\n"
            f"### 當前數據緩存 ###\n{raw_data[:3000]}\n\n"
            f"### 歷史對話摘要 ###\n{state['messages'][-3:]}\n\n"
            f"### 用戶最新要求 ###\n{state['input_message']}\n\n"
            "【任務目標】\n"
            "1. **靈活統計 (Statistics)**：\n"
            "   - 根據要求計算任何數值：平均值 (Avg)、最大值 (Max)、最小值 (Min)、標準差、或是變化趨勢。\n"
            "   - 若用戶要求「對比」，請比較不同時段的平均數值。\n\n"
            "2. **分析回報**：\n"
            "   - 用專業醫學口吻解釋統計結果（例如：這段期間的收縮壓平均為 135mmHg，處於偏高水平）。\n"
            "   - 若數據不足以分析，請禮貌告知並建議用戶增加測量頻率。\n\n"
            "3. **風險標記**：\n"
            "   - 請根據規範分析數據。若出現任何一項『異常』(BP, SpO2, Temp)，結尾必須包含 [EMERGENCY] 或 [NORMAL]。"
        )
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
        is_emergency = "[EMERGENCY]" in res.content
        clean_content = res.content.replace("[EMERGENCY]", "").replace("[NORMAL]", "")

        if can_visualize:
            clean_content += "\n\n💡 **需要我為您繪製趨勢分析圖表嗎？**"

        return {
            "final_response": clean_content,
            "is_emergency": is_emergency,
            "context_data": raw_data,
        }

    async def node_emergency_advice(self, state: AgentState):
        """
        緊急建議節點：提供標準化的臨床 SOP。
        """
        prompt = (
            "### 臨床風險警示 ###\n"
            "當前檢測到用戶血壓數據已達臨床警戒水位。\n"
            "請提供標準化的醫學建議（靜坐休息、必要時就醫）。"
        )
        res = await self.llm.ainvoke(prompt)
        return {
            "final_response": f"{state['final_response']}\n\n--- ⚠️ 建議 ---\n{res.content}"
        }
