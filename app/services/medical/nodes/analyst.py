import json
from app.services.tools.medical_tools import get_user_health_data
from app.services.tools.system_tools import load_specialized_skill
from app.services.medical.state import AgentState

from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


class HealthAnalystNodes:
    def __init__(self, llm):
        self.llm = llm

    async def node_health_analyst(self, state: AgentState):
        skill_info = load_specialized_skill.invoke({"skill_name": "health_analyst"})
        raw_data = state.get("context_data") or get_user_health_data.invoke(
            {"user_id": state["user_id"]}
        )
        if not raw_data:
            raw_data = get_user_health_data.invoke({"user_id": state["user_id"]})
        prompt = (
            f"### 專業規範 ###\n{skill_info}\n\n"
            f"### 當前數據緩存 ###\n{raw_data[:2000]}\n\n"
            f"### 歷史對話摘要 ###\n{state['messages'][-3:]}\n\n"
            f"### 用戶最新要求 ###\n{state['input_message']}\n\n"
            "【任務目標】\n"
            "請根據用戶的「最新要求」與「歷史對話」，對「當前數據」執行精準的處理：\n\n"
            "1. **動態過濾 (Filtering)**：\n"
            "   - 若用戶提到特定時間（如：某月、某季、去年、上週），請過濾數據中的 timestamp。\n"
            "   - 若用戶提到特定指標（如：只要看血氧），請過濾 JSON 欄位。\n\n"
            "2. **靈活統計 (Statistics)**：\n"
            "   - 根據要求計算任何數值：平均值 (Avg)、最大值 (Max)、最小值 (Min)、標準差、或是變化趨勢。\n"
            "   - 若用戶要求「對比」，請比較不同時段的平均數值。\n\n"
            "3. **分析回報**：\n"
            "   - 用專業醫學口吻解釋統計結果（例如：這段期間的收縮壓平均為 135mmHg，處於偏高水平）。\n"
            "   - 若數據不足以分析，請禮貌告知並建議用戶增加測量頻率。\n\n"
            "4. **風險標記**：\n"
            "   - 請根據規範分析數據。若出現任何一項『異常』(BP, SpO2, Temp)，結尾必須包含 [EMERGENCY] 或 [NORMAL]。"
        )
        res = await self.llm.ainvoke(prompt)
        # 邏輯判斷：計算數據量是否足以繪圖
        data_list = json.loads(raw_data).get("history", [])
        can_visualize = len(data_list) >= 5

        logger.debug(f"[LLM Raw] 分析師回覆原文: {res.content}")
        is_emergency = "[EMERGENCY]" in res.content
        logger.info(f"[Risk Analysis] 是否觸發緊急狀態: {is_emergency}")
        clean_content = res.content.replace("[EMERGENCY]", "").replace("[NORMAL]", "")
        if can_visualize:
            clean_content += "\n\n💡 **需要我為您繪製趨勢分析圖表嗎？**"

        return {
            "final_response": clean_content,
            "is_emergency": is_emergency,
            "context_data": raw_data,
        }

    async def node_emergency_advice(self, state: AgentState):
        # 緊急建議通常是固定的標準作業程序 (SOP)
        prompt = (
            "### 臨床風險警示 ###\n"
            "當前檢測到用戶血壓數據已達臨床警戒水位。\n"
            "請提供標準化的醫學建議：\n"
            "1. 建議用戶保持平靜，靜坐 15 分鐘後重新測量。\n"
            "2. 若伴隨頭痛、胸痛等症狀，建議立即尋求專業醫療協助或撥打緊急電話。"
        )
        res = await self.llm.ainvoke(prompt)
        return {
            "final_response": f"{state['final_response']}\n\n--- ⚠️ 建議 ---\n{res.content}"
        }
