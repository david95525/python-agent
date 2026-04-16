# app/api/api_router.py
import json
from contextlib import asynccontextmanager
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.medical.service import MedicalAgentService
from app.services.financial_service import FinancialAgentService

from app.utils.logger import setup_logger
import time

# 建立路由物件
router = APIRouter()

logger = setup_logger("ApiRouter")


# 定義請求模型
class ChatRequest(BaseModel):
    message: str
    userId: str = "default-user"


class InvestRequest(BaseModel):
    symbol: str
    context: str = ""


_medical_service = MedicalAgentService()
_financial_agent = FinancialAgentService()


@asynccontextmanager
async def lifespan(app):
    """
    封裝所有服務相關的生命週期邏輯。
    """
    logger.info("[Lifespan] 系統服務準備就緒")
    yield
    logger.info("[Lifespan] 正在關閉所有服務資源...")
    await _medical_service.close()
    if hasattr(_financial_agent, "close"):
        await _financial_agent.close()


@router.post("/chat")
async def chat(request: ChatRequest):
    logger.info(f"[Request] 收到聊天請求 (串流模式) - User: {request.userId}")

    async def event_generator():
        try:
            # 呼叫後端服務 (Async Generator)
            async for event in _medical_service.handle_chat(request.userId, request.message):
                # 每個 event 都是 dict，將其轉為 JSON 字串並以 Server-Sent Events (SSE) 格式發送
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[Streaming Error] {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/deep-research/invest/manual")
async def invest_manual(payload: InvestRequest):
    """
    手動模式投資決策端點(LangGraph)
    """
    logger.info(f"[API] 收到深度研究請求: {payload.symbol}")
    try:
        # 呼叫金融分析服務
        result = await _financial_agent.run_manual_logic(payload.symbol)

        logger.info(f"[API] {payload.symbol} 分析完成")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"[API] 深度分析失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="深度分析過程發生異常")


@router.post("/deep-research/invest/official")
async def invest_official(payload: InvestRequest):
    """封裝路徑 (DeepAgents)"""
    try:
        result = await _financial_agent.run_official_deep_logic(payload.symbol)
        return {"mode": "Official DeepAgents", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
