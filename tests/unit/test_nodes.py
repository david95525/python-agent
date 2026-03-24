import pytest
import json
from langchain_core.messages import AIMessage, ToolMessage
from app.services.medical.nodes.router import RouterNode
from app.services.medical.nodes.analyst import HealthAnalystNodes


from unittest.mock import MagicMock, AsyncMock
from app.services.medical.nodes.router import RouterNode, RouterOutput

# ------------------------------------------------------------------
# 1. 測試 RouterNode (使用 Unified Router)
# ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_router_logic_and_llm_intent(mock_state):
    # 場景 A：測試硬編碼攔截 (用戶同意畫圖)
    fake_llm = MagicMock()
    router = RouterNode(llm=fake_llm,
                        manifest="...",
                        valid_ids=["visualizer", "general"])

    mock_state["messages"] = [AIMessage(content="需要我為您繪製趨勢分析圖表嗎？")]
    mock_state["input_message"] = "好啊，幫我畫"

    res_confirm = await router.node_router(mock_state)
    assert res_confirm["intent"] == "visualizer"

    # 場景 B：測試 LLM 正常判斷 (Structured Output)
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=RouterOutput(
        intent="health_analyst",
        query_start="2026-01-01",
        query_end="2026-01-07",
        reasoning="用戶詢問血壓狀態"
    ))
    fake_llm.with_structured_output.return_value = mock_structured_llm
    
    router_llm = RouterNode(llm=fake_llm,
                            manifest="...",
                            valid_ids=["health_analyst"])

    mock_state["messages"] = []
    mock_state["input_message"] = "我最近血壓正常嗎？"

    res_query = await router_llm.node_router(mock_state)
    assert res_query["intent"] == "health_analyst"
    assert res_query["query_start"] == "2026-01-01"


# ------------------------------------------------------------------
# 3. 測試 HealthAnalyst (緊急狀況識別)
# ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_analyst_emergency_flag(fake_llm_factory, mock_state):
    # 模擬 LLM 發現危險
    fake_llm = fake_llm_factory(["您的血壓過高！ [EMERGENCY] 請立即就醫。"])
    analyst_nodes = HealthAnalystNodes(llm=fake_llm)

    # 準備模擬數據
    mock_data = json.dumps({"history": [{"sys": 180, "dia": 110}], "total": 1})

    # 使用 mock_state 並更新內容
    mock_state.update({
        "context_data": mock_data,
        "input_message": "幫我分析",
        "query_start": "2026-01-01",
        "query_end": "2026-01-07",
        "data_count": 1
    })

    res = await analyst_nodes.node_health_analyst(mock_state)
    assert res["is_emergency"] is True
    assert "[EMERGENCY]" not in res["final_response"]
    assert "請立即就醫" in res["final_response"]


@pytest.mark.asyncio
async def test_analyst_handle_api_error(fake_llm_factory):
    # 模擬 API 故障的情況
    error_data = json.dumps({"status": "error", "message": "遠端伺服器回應異常"})

    # 建立一個模擬的 State，帶入錯誤訊息
    state = {
        "messages": [
            AIMessage(content="",
                      tool_calls=[{
                          "name": "get_user_health_data",
                          "args": {
                              "user_id": "test_user"
                          },
                          "id": "call_123"
                      }]),
            # 模擬工具回傳錯誤
            ToolMessage(content=error_data, tool_call_id="call_123")
        ]
    }
    fake_llm = fake_llm_factory(["不用真的回覆，因為我們會 Mock 工具結果"])
    node = HealthAnalystNodes(llm=fake_llm)
    result = await node.node_health_analyst(state)
    # 檢查回傳的鍵值是否正確
    assert "final_response" in result
    assert any(word in result["final_response"] for word in ["異常", "無法", "錯誤"])


@pytest.mark.asyncio
async def test_analyst_empty_history(fake_llm_factory, mock_state):
    # 模擬 API 回傳成功，但歷史紀錄是空的
    empty_data = json.dumps({"status": "success", "history": [], "total": 0})
    fake_llm = fake_llm_factory(["查無數據"])
    # 這裡我們甚至不需要 LLM，直接測分析邏輯
    node = HealthAnalystNodes(llm=fake_llm)

    # 模擬 state 進入分析節點
    mock_state["context_data"] = empty_data
    # 假設 node 裡有處理空數據的邏輯
    res = await node.node_health_analyst(mock_state)

    assert "找不到" in res["final_response"] or "量測紀錄" in res["final_response"]
