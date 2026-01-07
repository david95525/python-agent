## Python AI Agent (FastAPI + RAG + Tool Use)
這是一個基於 Python FastAPI 與 Gemini 2.0 Flash 構建的全功能 AI Agent 專案。 本專案由原有的 Node.js 版本遷移而來，旨在利用 Python 生態系更強大的 AI 工具鏈（LangChain Python, uv, FastAPI），打造一個具備私有知識庫能力的智能助手。

目前以「血壓計說明書」作為專業領域測試案例 (PoC)。

# 🚀 核心技術架構
LLM 模型: Google Gemini 2.0 Flash (支援高效能生成與 Tool Calling)

後端框架: FastAPI (支援高併發非同步處理)

包管理工具: uv (極速的 Python 套件與環境管理工具)

向量資料庫: PostgreSQL + pgvector (持久化儲存於 Docker 具名卷)

開發框架:

LangChain Python: 負責處理 PDF 解析、文本切片與向量對接。

Pydantic Settings: 嚴謹的環境變數與型別管理。

對話記憶: 實現了基於 Session 的 Context 注入，確保對話連貫性。

# 🛠️ 功能模組
RAG 知識檢索:

使用 scripts/ingest_pdf.py 將 PDF 切片並轉化為向量。

採用 Google text-embedding-004 模型確保檢索精準度。

非同步 API 接口:

基於 Python asyncio 實現，提供高效的 /chat 端點。

專業客服指令 (System Prompt):

嚴格的角色設定，專注於醫療器材領域，具備防禦性回覆機制。

環境持久化:

透過 Docker Volume 技術，確保資料庫內容不會隨重啟消失。

# 快速開始
1. 環境準備
建立 .env 檔案並設定以下變數：
程式碼片段
```
PORT=8000
ENVIRONMENT=development
GEMINI_API_KEY=key
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/postgres
```

2. 安裝與執行
使用 uv 快速安裝環境：

PowerShell

# 同步環境與依賴
uv sync

# 啟動帶有持久化磁碟卷的資料庫 (Docker)
```
docker volume create pg_vector_data
docker run --name pgvector -e POSTGRES_PASSWORD=你的密碼 -p 5432:5432 -v pg_vector_data:/var/lib/postgresql/data -d ankane/pgvector
```
# 啟用資料庫向量擴充 (初次需執行)
```
docker exec -it pgvector psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```
# 導入測試資料 (PDF)
```
uv run python scripts/ingest_pdf.py
```
# 啟動開發伺服器
```
uv run fastapi dev main.py
```

# 📝 測試案例
私有知識測試: 詢問「Microlife BP B3 的 AFIB 技術是什麼？」

錯誤代碼測試: 詢問「螢幕顯示 Err 2 是什麼意思？」

上下文記憶測試: 接著詢問「那該怎麼解決？」(測試 Agent 是否記得你在問 Err 2)

邊界防禦測試: 詢問「今天的台北天氣如何？」(預期會根據 System Prompt 禮貌拒絕回答非專業領域問題)

# 專案結構

app/: FastAPI 核心邏輯 (Routers, Services, Providers)

scripts/: 資料匯入與資料庫維護腳本

data/: 存放原始 PDF 說明書

pyproject.toml: 專案依賴管理 (uv)