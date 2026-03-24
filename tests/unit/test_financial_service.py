import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.financial_service import FinancialAgentService

@pytest.fixture
def financial_service(fake_llm_factory):
    with patch("app.services.financial_service.setup_logger"):
        with patch("app.services.financial_service.create_deep_agent"):
            service = FinancialAgentService()
            service.llm = fake_llm_factory(["測試回覆"])
            return service

@pytest.mark.asyncio
async def test_node_market_research(financial_service):
    # Mock tools
    with patch("app.services.financial_service.get_stock_price") as mock_price:
        with patch("app.services.financial_service.get_market_news") as mock_news:
            mock_price.invoke.return_value = "價格: 100"
            mock_news.invoke.return_value = "新聞: 漲停"
            
            state = {"symbol": "2330"}
            res = await financial_service.node_market_research(state)
            
            assert "data_raw" in res
            assert "價格: 100" in res["data_raw"]
            assert "新聞: 漲停" in res["data_raw"]
            # 檢查 symbol 轉換
            mock_price.invoke.assert_called_with({"symbol": "2330.TW"})

@pytest.mark.asyncio
async def test_node_risk_analysis(financial_service, fake_llm_factory):
    # Mock LLM for this test
    financial_service.llm = fake_llm_factory(["這是一個高風險的投資 [高]"])
    
    with patch("app.services.financial_service.load_specialized_skill") as mock_skill:
        mock_skill.invoke.return_value = "金融專家技能配置"
        
        state = {"data_raw": "一些數據"}
        res = await financial_service.node_risk_analysis(state)
        
        assert res["risk_level"] == "高"
        assert "這是一個高風險的投資" in res["analysis_report"]

@pytest.mark.asyncio
async def test_node_final_decision(financial_service, fake_llm_factory):
    # Mock LLM for this test
    financial_service.llm = fake_llm_factory(["最終建議：買入"])
    
    with patch("app.services.financial_service.load_specialized_skill") as mock_skill:
        mock_skill.invoke.return_value = "金融專家技能配置"
        
        state = {
            "symbol": "2330",
            "data_raw": "數據",
            "analysis_report": "分析"
        }
        res = await financial_service.node_final_decision(state)
        
        assert res["final_response"] == "最終建議：買入"
