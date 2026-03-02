from app.services.tools.system_tools import load_specialized_skill
from app.services.tools.medical_tools import (
    search_device_manual,
    plot_health_chart,
    get_user_health_data,
)
from app.schemas.agent import ChartParams
from app.services.medical.state import AgentState
from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


class ExpertNodes:
    def __init__(self, llm):
        self.llm = llm

    async def node_device_expert(self, state: AgentState):
        """硬體專家節點：專注於 RAG 檢索"""
        # 動態加載Skills
        skill_content = load_specialized_skill.invoke({"skill_name": "device_expert"})
        # 執行 RAG
        raw_info = await search_device_manual.ainvoke({"query": state["input_message"]})
        logger.info(f"[RAG] 檢索完成，獲取資料長度: {len(raw_info)} 字元")
        prompt = (
            f"### 專業設備知識庫 ###\n{raw_info}\n\n"
            f"### 之前討論的設備 ###\n{state.get('active_focus', {}).get('device_name', '未知')}\n\n"
            f"### 用戶追問 ###\n{state['input_message']}\n\n"
            "指令：請結合上下文與說明書，精確回答用戶關於該設備的追問。如果用戶提到了新的代碼或功能，請從知識庫中檢索並解釋。"
        )
        res = await self.llm.ainvoke(prompt)
        return {"final_response": res.content}

    async def node_visualizer(self, state: AgentState):
        """繪圖專家節點：動態判斷指標並調用工具產出圖表"""
        # 取得數據
        raw_data = state.get("context_data")
        if not raw_data:
            raw_data = get_user_health_data.invoke({"user_id": state["user_id"]})
            logger.warning(
                f"[Visualizer] State 中無數據，已重新抓取用戶 {state['user_id']} 數據"
            )
        # 取得用戶當前的需求
        user_intent = state["input_message"]

        # 使用 with_structured_output 確保 LLM 回傳的是 ChartParams 物件而非字串
        structured_llm = self.llm.with_structured_output(ChartParams)
        # 升級指令：讓 LLM 決定要畫什麼指標
        # 注意：這裡我們傳入 raw_data 的範例，讓 LLM 知道有哪些欄位可用
        data_sample = raw_data[:500]  # 擷取部分數據供 LLM 參考
        visualizer_prompt = (
            "你是一位資深的『數據視覺化專家』。\n"
            f"【用戶當前需求】：{user_intent}\n\n"  # 告訴 AI 用戶要看什麼
            f"【數據樣本內容】：{data_sample}\n\n"
            "【決策準則】：\n"
            "1. 指標精選：請嚴格根據『用戶當前需求』決定繪製的 columns。\n"
            "   - 若用戶說『只要看收縮壓』，columns 僅能包含 ['sys']。\n"
            "   - 若用戶未指定，則根據數據常規 (如: ['sys', 'dia']) 繪製。\n"
            "2. 類型挑選：趨勢用 'line'，對比用 'bar'。\n"
            "3. 標題與單位：標題需專業且對應指標，單位需正確。"
        )

        # 獲取 LLM 決策
        params: ChartParams = await structured_llm.ainvoke(visualizer_prompt)
        # 執行繪圖工具 (傳入動態參數)
        chart_base64 = plot_health_chart.invoke(
            {
                "data": raw_data,
                "title": params.title,
                "chart_type": params.chart_type,
                "columns": params.columns,
                "labels": params.labels,
                "unit": params.unit,
            }
        )

        # 封裝回傳
        chart_type_zh = {"line": "折線", "bar": "長條", "scatter": "散佈"}.get(
            params.chart_type, "趨勢"
        )
        final_text = (
            f"**已根據您的要求生成{chart_type_zh}圖表**：\n"
            f"分析指標：{', '.join(params.labels)}\n\n"
            f"![Health Chart]({chart_base64})"
        )

        return {"final_response": final_text}
