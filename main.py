import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.api_router import router as api_router, lifespan
from app.utils.logger import setup_logger

logger = setup_logger("MainApp")

app = FastAPI(title="AI Agent Research Lab", lifespan=lifespan)

# 註冊 API 路由
app.include_router(api_router, prefix="/api/v1", tags=["API"])

# 路由


@app.get("/")
async def index():
    logger.info("存取總導覽頁")
    return FileResponse("static/index.html")


@app.get("/chat")
async def chat_page():
    logger.info("進入 Agent 聊天實驗室")
    return FileResponse("static/chat.html")


@app.get("/deep")
async def deep_page():
    logger.info("進入 Deep Agent 研究區")
    return FileResponse("static/deep.html")


# 靜態檔案掛載
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    is_local = os.environ.get("ENV") == "development" or "PORT" not in os.environ
    listen_host = "0.0.0.0"

    if is_local:
        logger.info(f"本地開發模式，監聽: http://{listen_host}:{port}")
        # 注意：使用 reload=True 時，字串形式 "main:app" 是必須的
        uvicorn.run("main:app", host=listen_host, port=port, reload=True)
    else:
        logger.info(f"雲端環境模式，監聽: http://{listen_host}:{port}")
        uvicorn.run(app, host=listen_host, port=port, reload=False)
