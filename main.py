import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.api_router import router as api_router
from app.utils.logger import setup_logger

# 初始化 Logger
logger = setup_logger("MainApp")

app = FastAPI(title="AI Agent Research Lab")

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
    return FileResponse("static/deep_agent.html")


# 靜態檔案掛載
app.mount("/static", StaticFiles(directory="static"), name="static")

# 啟動邏輯
port = int(os.environ.get("PORT", 8000))
# 判斷是否為本地開發環境
is_local = os.environ.get("ENV") == "development" or "PORT" not in os.environ

if __name__ == "__main__":
    mode_str = "Local" if is_local else "Cloud"
    logger.info(f"AI Lab 正在以 {mode_str} 模式啟動...")

    # 關鍵修改：在 Docker 環境中，host 必須是 0.0.0.0
    # 我們可以直接判斷是否在 Docker 中，或者簡單地在所有非 Cloud 模式也嘗試監聽 0.0.0.0
    listen_host = "0.0.0.0"

    if is_local:
        logger.info(f"本地開發模式，監聽: http://{listen_host}:{port}")
        # Local 模式使用 reload
        uvicorn.run("main:app", host=listen_host, port=port, reload=True)
    else:
        logger.info(f"雲端環境模式，監聽: http://{listen_host}:{port}")
        # 雲端模式關閉 reload
        uvicorn.run("main:app", host=listen_host, port=port, reload=False)
