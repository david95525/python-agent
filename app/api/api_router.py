# app/api/api_router.py
from contextlib import asynccontextmanager
from fastapi import APIRouter, HTTPException
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
    app 參數是 FastAPI 實體，雖然這裡用不到，但這是標準格式。
    """
    # 啟動時邏輯 (選填)
    logger.info("[Lifespan] 系統服務準備就緒")
    yield
    logger.info("[Lifespan] 正在關閉所有服務資源...")
    await _medical_service.close()
    if hasattr(_financial_agent, "close"):  # 確保金融服務也有定義 close
        await _financial_agent.close()


@router.post("/chat")
async def chat(request: ChatRequest):
    start_time = time.time()
    logger.info(f"[Request] 收到聊天請求 - User: {request.userId}")

    try:
        # 呼叫後端服務
        result_data = await _medical_service.handle_chat(
            request.userId, request.message)

        # --- 關鍵防禦機制：檢查 result_data 是否為字典 ---
        if isinstance(result_data, str):
            # 如果 Service 因為 Exception 回傳了字串，轉化為 error 結構
            logger.warning(f"[Service Warning] 收到非結構化回覆: {result_data}")
            return {
                "status": "error",
                "message": result_data,
                "data": {
                    "text": result_data,
                    "intent": "error",
                    "graph": ""
                },
            }

        process_time = time.time() - start_time

        # 安全地使用 .get()，提供預設值
        intent = result_data.get("intent", "unknown")
        text = result_data.get("text", "無回覆內容")
        graph = result_data.get("graph", "")

        logger.info(
            f"[Response] 處理成功 - Intent: {intent} | 耗時: {process_time:.2f}s")

        return {
            "status": "success",
            "data": {
                "text": text,
                "graph": graph,
                "intent": intent,
                "ui_data": result_data.get("ui_data"),
                "is_emergency": result_data.get("is_emergency", False)
            },
        }

    except Exception as e:
        logger.error(f"[API Error] 處理失敗: {str(e)}", exc_info=True)
        # 即使發生最嚴重的崩潰，也回傳 JSON 格式而非直接拋出 HTTPException（視前端需求而定）
        return {"status": "error", "message": "Agent 內部執行錯誤，請檢查伺服器日誌。"}


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
