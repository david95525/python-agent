from app.services.tools.system_tools import load_specialized_skill
from app.services.tools.medical_tools import (
    get_device_knowledge,
    plot_health_chart,
    get_user_health_data,
)
from app.schemas.agent import ChartParams
from app.services.medical.state import AgentState
from app.utils.logger import setup_logger

logger = setup_logger("AgentService")


from app.utils.prompt_manager import prompt_manager

class ExpertNodes:
    def __init__(self, llm):
        self.llm = llm

    async def node_device_expert(self, state: AgentState):
        """硬體專家節點：專注於 RAG 檢索"""
        # 執行 RAG
        raw_info = await get_device_knowledge.ainvoke({"query": state["input_message"]})
        logger.info(f"[RAG] 檢索完成，獲取資料長度: {len(raw_info)} 字元")
        
        # 從 State 讀取已經載入好的技能指令 (由 Router 準備)
        skill_content = state.get("skill_instructions") or "請根據設備知識庫回答用戶問題。"
        
        # 使用 PromptManager 模板
        prompt_template = prompt_manager.get_template("device_expert")
        full_prompt = prompt_template.format_messages(
            raw_info=raw_info,
            active_device=state.get('active_focus', {}).get('device_name', '未知'),
            input_message=state['input_message']
        )
        
        # 將 skill_content 合併到 System Message 中 (另一種優化方式)
        # 這裡暫時維持原 PromptManager 結構，但邏輯已從 State 獲取
        res = await self.llm.ainvoke(full_prompt)
        return {"final_response": res.content}

    async def node_visualizer(self, state: AgentState):
        """繪圖專家節點：動態判斷指標並調用工具產出圖表"""
        # 取得數據
        raw_data = state.get("context_data")
        if not raw_data:
            raw_data = await get_user_health_data.ainvoke({"user_id": state["user_id"]})
            logger.warning(
                f"[Visualizer] State 中無數據，已重新抓取用戶 {state['user_id']} 數據"
            )
        # 取得用戶當前的需求
        user_intent = state["input_message"]
        analysis_summary = state.get("analysis_summary", "無先前的分析紀錄")

        # 使用 with_structured_output 確保 LLM 回傳的是 ChartParams 物件而非字串
        structured_llm = self.llm.with_structured_output(ChartParams)
        # 升級指令：讓 LLM 決定要畫什麼指標，並參考先前的分析結果
        data_sample = raw_data[:500]  # 擷取部分數據供 LLM 參考
        
        # 使用 PromptManager 模板
        prompt_template = prompt_manager.get_template("visualizer")
        full_prompt = prompt_template.format_messages(
            user_intent=user_intent,
            analysis_summary=analysis_summary,
            data_sample=data_sample
        )

        # 獲取 LLM 決策
        params: ChartParams = await structured_llm.ainvoke(full_prompt)
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
