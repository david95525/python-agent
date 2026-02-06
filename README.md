## Python AI Medical Agent (FastAPI + RAG + Skill Injection)
這是一個基於 FastAPI 與 Gemini 2.5 Flash 構建的全功能 AI Agent 專案。本專案實現了私有知識庫 (RAG)、動態專業技能注入 (Skill Injection) 與生理數據分析能力，旨在提供符合醫療標準的智能輔助體驗。

# 🚀 核心技術架構
LLM 模型: Google Gemini 2.5 Flash (支援強大的原生 Tool Calling 與長文本推理)。

後端框架: FastAPI (異步高併發處理) + LangChain/LangGraph (Agent 思考鏈)。

向量資料庫: PostgreSQL + pgvector (在地化語意搜尋與向量存儲)。

技能系統: 實作動態 Skill Injection 機制，將 skills/ 下的專業規範（如醫療倫理、輸出格式）動態注入 System Prompt。

部署管理: uv (Python 封裝與依賴管理) + Docker Compose (基礎設施一鍵啟動)。

# 🛠️ 功能模組
1. RAG 知識檢索 (search_device_manual)
針對血壓計說明書進行 PDF 解析、語意切片與向量化。

智慧對齊: 自動將用戶口語（如 "Err 3"）優化為結構化關鍵字，提升檢索精準度。

2. 生理數據分析 (get_user_health_data)
獲取用戶歷史健康紀錄，計算趨勢、平均值並識別異常波動。

對照說明書醫學標準（如 135/85 mmHg）提供衛教建議。

3. 動態技能注入 (get_skill_content)
人格設定: 讀取 skills/*.md 檔案，確保 Agent 行為符合「專業、嚴謹、具備免責聲明」的規範。

# 快速開始
1. 環境準備
建立 .env 檔案並設定以下變數：
程式碼片段
```
PORT=8000
ENVIRONMENT=production
GEMINI_API_KEY=你的Gemini金鑰
# 注意：在 Docker 內部連線時，主機名應為 db
DATABASE_URL=postgresql+psycopg://postgres:你的密碼@db:5432/postgres
DB_USER=postgres
DB_PASSWORD=你的密碼
DB_NAME=postgres
```

2. 使用 Docker Compose 一鍵部署 (推薦)
本專案已完成容器化配置，解決了 Windows 權限與網路監聽問題：
```
# 建置鏡像並啟動服務 (自動包含 pgvector 與 FastAPI)
docker compose up -d --build

# (選配) 第一次執行時手動檢查擴充功能是否存在
docker compose exec db psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 導入測試資料 (PDF 向量化)
# 程式會自動檢查表是否存在並初始化 pgvector
docker compose exec agent python ingest_pdf.py
```

3. 安裝與執行
使用 uv 快速安裝環境：
```
# 安裝依賴
uv sync

# 啟動開發伺服器 (監聽 0.0.0.0 確保 Docker/外部可連線)
uv run fastapi dev main.py --host 0.0.0.0
```

# 📝 測試案例
測試場景	詢問範例	預期 Agent 行為
私有知識	"Err 3 是什麼意思？"	檢索 PDF，回答「壓脈帶充氣錯誤」並提供排除步驟。
數據分析	"分析我最近的血壓趨勢。"	調用數據工具，對比數值並給予健康判讀。
邊界防禦	"推薦今天的股票。"	觸發 Medical-Expert 規範，禮貌拒絕回答醫療以外問題。
法律免責	(任何建議後)	自動附加「本建議僅供參考，不具醫療診斷效力。」

# 專案結構

app/services/tools/: 核心工具集（RAG 檢索、數據查詢、技能加載）。

skills/: 存放 Markdown 格式的行為準則與人格設定。

data/: 存放原始 PDF 醫療器材說明書。

static/: 前端研究室介面 (index.html, chat.html)。

ingest_pdf.py: 自動化資料清洗、切片與向量化存儲腳本。

docker-compose.yml: 定義服務拓撲與 Named Volumes 持久化配置。