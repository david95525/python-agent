import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.medical_demo_service import MedicalDemoService, AnalysisResponse, DateRange

@pytest.fixture
def medical_demo_service():
    with patch("app.services.medical_demo_service.setup_logger"):
        service = MedicalDemoService()
        # Mock LLM
        service.llm = MagicMock()
        return service

@pytest.mark.asyncio
async def test_run_demo_chat_success(medical_demo_service):
    # 1. Mock SQLChatMessageHistory
    mock_history = MagicMock()
    mock_history.messages = []
    
    # 2. Mock DateRange analysis
    mock_date_analyzer = MagicMock()
    mock_date_analyzer.ainvoke = AsyncMock(return_value=DateRange(start_date="2026-01-01", end_date="2026-01-07"))
    
    # 3. Mock AnalysisResponse structured output
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=AnalysisResponse(
        summary="測試分析",
        data_list=[],
        mode="list"
    ))
    
    # 配置 LLM 的 with_structured_output 傳回值
    def side_effect(output_schema):
        if output_schema == DateRange:
            return mock_date_analyzer
        if output_schema == AnalysisResponse:
            return mock_structured_llm
        return MagicMock()
    
    medical_demo_service.llm.with_structured_output.side_effect = side_effect

    # Mock chain ainvoke
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=AnalysisResponse(
        summary="測試分析",
        data_list=[],
        mode="list"
    ))

    with patch.object(medical_demo_service, "_get_chat_history", return_value=mock_history):
        with patch("app.services.medical_demo_service.get_user_health_data") as mock_tool:
            with patch("app.services.medical_demo_service.ChatPromptTemplate.from_messages") as mock_prompt:
                # 模擬 prompt | structured_llm 回傳 mock_chain
                mock_prompt.return_value.__or__.return_value = mock_chain
                mock_tool.ainvoke = AsyncMock(return_value='{"data": []}')
                
                result = await medical_demo_service.run_demo_chat("user123", "測試問題")
                
                # 驗證結果
                res_dict = json.loads(result)
                assert res_dict["summary"] == "測試分析"
            
            # 驗證歷史紀錄被調用
            mock_history.add_user_message.assert_called_with("測試問題")
            mock_history.add_ai_message.assert_called_with("測試分析")

@pytest.mark.asyncio
async def test_run_demo_chat_error(medical_demo_service):
    # 模擬異常
    medical_demo_service.llm.with_structured_output.side_effect = Exception("LLM Error")
    
    with patch.object(medical_demo_service, "_get_chat_history"):
        result = await medical_demo_service.run_demo_chat("user123", "測試問題")
        res_dict = json.loads(result)
        assert "錯誤" in res_dict["summary"]
        assert res_dict["mode"] == "error"
