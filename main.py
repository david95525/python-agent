from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.chat_router import router as chat_router  # 匯入剛寫好的 router

app = FastAPI(title="AI Agent Gateway")

# 註冊路由
app.include_router(chat_router)

@app.get("/")
async def index():
    return FileResponse("static/index.html")

# 掛載靜態檔案
app.mount("/", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)