from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.agent_service import AgentService

# 建立路由物件，這就像一個「子路由容器」
router = APIRouter()
agent_service = AgentService()


class ChatRequest(BaseModel):
    message: str
    userId: str = "default-user"


# 使用 @router 替代 @app
@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        result_data = await agent_service.handle_chat(request.userId,
                                                      request.message)
        return {
            "status": "success",
            "data": {
                "text": result_data["text"],
                "graph": result_data["graph"],
                "intent": result_data["intent"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
