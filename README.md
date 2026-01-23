## Python AI Medical Agent (FastAPI + RAG + Skill Injection)
這是一個基於 FastAPI 與 Gemini 2.0 Flash 構建的全功能 AI Agent 專案。本專案利用 Python 生態系強大的 AI 工具鏈，實現了一個具備私有知識庫 (RAG)、動態專業技能 (Skill Injection) 與歷史數據分析能力的智能醫療助手。

# 🚀 核心技術架構
LLM 模型: Google Gemini 2.0 Flash (支援高效能 Tool Calling)。

後端框架: FastAPI (異步處理) + LangGraph (Agent 決策流)。

向量資料庫: PostgreSQL + pgvector (支援語意搜尋)。

技能系統: 實作了 Skill Injection 機制，將專業領域規範（如 medical-expert.md）動態注入 System Prompt，確保 Agent 行為符合醫療倫理與專業標準。

開發工具: uv (極速環境管理)、Docker (資料庫持久化)。

# 🛠️ 功能模組
1. RAG 知識檢索 (search_device_manual)
精準對接: 針對血壓計說明書進行 PDF 解析與向量化。

容錯處理: 自動將簡單的錯誤代碼（如 ERR3）優化為結構化搜尋詞，提升檢索召回率。

2. 生理數據分析 (get_user_health_data)
趨勢判讀: 支援獲取用戶歷史紀錄，並能計算平均值、識別異常波動。

專業對照: 結合說明書標準（如 135/85 mmHg 警戒線）提供健康建議。

3. 動態技能注入 (get_skill_content)
內人格設定: 透過讀取 skills/ 目錄下的 Markdown 檔案，將專業指引（任務指令、輸出規範、免責聲明）直接注入 Agent 意識層。

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
# 建立卷並啟動 pgvector
docker volume create pg_vector_data
docker run --name pgvector -e POSTGRES_PASSWORD=你的密碼 -p 5432:5432 -v pg_vector_data:/var/lib/postgresql/data -d ankane/pgvector
# 啟用擴充
docker exec -it pgvector psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```
# 導入測試資料 (PDF)
```
uuv run python ingest_pdf.py  # 匯入說明書
```
# 啟動開發伺服器
```
uv sync
uv run fastapi dev main.py           # 啟動服務
```

# 📝 測試案例
測試場景	詢問範例	預期 Agent 行為
私有知識	"ERR3 是什麼意思？"	執行 search_device_manual，回答「壓脈帶漏氣」。
數據分析	"分析我 2025 年底的血壓。"	執行 get_user_health_data，對比年初數據並給予建議。
邊界防禦	"今天台北天氣如何？"	根據 medical-expert 規範，禮貌拒絕回答非專業領域問題。
法律免責	(任何健康建議後)	自動附加「本建議僅供參考，不具醫療診斷效力。」

# 專案結構

app/services/tools/: 核心工具集（RAG、數據分析、系統技能載入）。

skills/: 存放各種專業領域的行為準則 (medical-expert.md)。

data/: 存放原始 PDF 說明書。

ingest_pdf.py: 資料匯入與資料庫向量化維護腳本。

main.py: FastAPI 啟動入口。