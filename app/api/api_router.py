from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.agent_service import AgentService
from app.utils.logger import setup_logger
import time

# 建立路由物件
router = APIRouter()
agent_service = AgentService()

# 初始化專屬 Logger
logger = setup_logger("ApiRouter")


class ChatRequest(BaseModel):
    message: str
    userId: str = "default-user"


@router.post("/chat")
async def chat(request: ChatRequest):
    #   記錄請求進入與原始資料
    start_time = time.time()
    logger.info(f"[Request] 收到聊天請求 - User: {request.userId}")
    logger.debug(f"[Payload] Message: {request.message}")

    try:
        # 呼叫後端服務
        result_data = await agent_service.handle_chat(request.userId,
                                                      request.message)

        # 計算處理耗時
        process_time = time.time() - start_time

        # 記錄處理結果 (使用 DEBUG 記錄複雜的 Graph)
        logger.info(
            f"[Response] 處理成功 - Intent: {result_data.get('intent')} | 耗時: {process_time:.2f}s"
        )
        logger.debug(
            f"[Graph Data] Mermaid 長度: {len(result_data.get('graph', ''))}")

        return {
            "status": "success",
            "data": {
                "text": result_data["text"],
                "graph": result_data["graph"],
                "intent": result_data["intent"]
            }
        }

    except Exception as e:
        # 錯誤處理：一定要包含 exc_info 以便追蹤堆疊
        logger.error(f"[API Error] 處理失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Agent 內部執行錯誤，請檢查伺服器日誌。")
