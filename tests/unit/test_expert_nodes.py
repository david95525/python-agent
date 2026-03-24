import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.medical.nodes.expert import ExpertNodes
from app.schemas.agent import ChartParams

@pytest.fixture
def expert_nodes():
    llm = MagicMock()
    return ExpertNodes(llm)

@pytest.mark.asyncio
async def test_node_device_expert(expert_nodes):
    expert_nodes.llm.ainvoke = AsyncMock(return_value=MagicMock(content="專家回覆"))
    with patch("app.services.medical.nodes.expert.load_specialized_skill") as mock_skill:
        mock_skill.invoke.return_value = "設備專家技能"
        with patch("app.services.medical.nodes.expert.get_device_knowledge") as mock_knowledge:
            mock_knowledge.ainvoke = AsyncMock(return_value="設備知識內容")
            
            state = {
                "input_message": "如何使用血壓計？",
                "active_focus": {"device_name": "血壓計"}
            }
            res = await expert_nodes.node_device_expert(state)
            
            assert res["final_response"] == "專家回覆"
            mock_knowledge.ainvoke.assert_called_with({"query": "如何使用血壓計？"})

@pytest.mark.asyncio
async def test_node_visualizer(expert_nodes):
    # Mock LLM with structured output
    mock_structured_llm = MagicMock()
    params = ChartParams(
        title="血壓趨勢",
        chart_type="line",
        columns=["sys", "dia"],
        labels=["收縮壓", "舒張壓"],
        unit="mmHg"
    )
    mock_structured_llm.ainvoke = AsyncMock(return_value=params)
    expert_nodes.llm.with_structured_output.return_value = mock_structured_llm
    
    with patch("app.services.medical.nodes.expert.plot_health_chart") as mock_plot:
        mock_plot.invoke.return_value = "base64_chart_data"
        
        state = {
            "user_id": "user123",
            "input_message": "幫我畫圖",
            "context_data": json.dumps([{"sys": 120, "dia": 80}])
        }
        res = await expert_nodes.node_visualizer(state)
        
        assert "base64_chart_data" in res["final_response"]
        assert "血壓趨勢" in str(mock_plot.invoke.call_args)
