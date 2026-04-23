# main.py
import uvicorn
import os
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.api_router import router as api_router, lifespan
from app.api.test_router import router as test_router
from app.utils.logger import setup_logger
from app.core.config import settings

logger = setup_logger("MainApp")

app = FastAPI(title="AI Agent Research Lab", lifespan=lifespan)

# 設定 CORS
if settings.backend_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.backend_cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 安全標頭中間件
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# 動態配置腳本：讓前端取得 API Token
@app.get("/api/v1/env-config.js")
async def get_env_config(request: Request):
    """
    動態生成 JS 腳本，將後端的 app_auth_token 注入到前端。
    安全性：檢查 Referer 是否來自允許的網域。
    """
    referer = request.headers.get("referer")
    # 簡單檢查：如果 Referer 存在且不包含您的 domain，可以拒絕 (本地測試時 referer 可能為空)
    is_allowed = not referer or (settings.app_domain and settings.app_domain in referer)
    
    # 開放開發環境下的本地測試
    if not is_allowed and settings.environment == "development":
        if referer and ("localhost" in referer or "127.0.0.1" in referer):
            is_allowed = True
            
    if not is_allowed:
        return Response(
            content="console.error('Unauthorized domain: ' + window.location.origin);", 
            status_code=403, 
            media_type="application/javascript"
        )
    
    config_js = f"window.ENV = {{ APP_AUTH_TOKEN: '{settings.app_auth_token}' }};"
    return Response(content=config_js, media_type="application/javascript")

# 註冊 API 路由
app.include_router(api_router, prefix="/api/v1", tags=["API"])
app.include_router(test_router, prefix="/api/test", tags=["QA Testing"])
# 路由


@app.get("/")
async def index():
    logger.info("存取總導覽頁")
    return FileResponse("static/index.html")


# QA 儀表板
@app.get("/qa")
async def qa_dashboard():
    logger.info("品管部門進入自動化測試儀表板")
    return FileResponse("static/test_dashboard.html")


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
    is_local = os.environ.get(
        "ENV") == "development" or "PORT" not in os.environ
    listen_host = "0.0.0.0"

    if is_local:
        logger.info(f"本地開發模式，監聽: http://{listen_host}:{port}")
        # 注意：使用 reload=True 時，字串形式 "main:app" 是必須的
        uvicorn.run("main:app", host=listen_host, port=port, reload=True)
    else:
        logger.info(f"雲端環境模式，監聽: http://{listen_host}:{port}")
        uvicorn.run(app, host=listen_host, port=port, reload=False)
