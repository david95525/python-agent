## AI Deep Research Platform (Finance & Medical)
基於 FastAPI + Gemini 2.5 Flash + LangGraph 的自主代理平台
本專案是一個集成了 DeepAgents (官方自主代理) 與 LangGraph (自定義思考鏈) 的先進 AI 系統。它不僅能處理私有醫療知識庫 (RAG)，還能針對金融標的進行即時深度研究。

# 🚀 核心進化與技術亮點
雙模式研究架構：

官方模式 (Official DeepAgents)：利用 Gemini 的原生 Tool Calling 進行自主規劃與工具調用。

手動模式 (Manual LangGraph)：透過顯式定義「研究-風險分析-決策」節點，實現可控且透明的思考鏈。

動態技能注入 (Skill Injection)：透過讀取 skills/*.md，動態賦予 Agent 不同領域（如：financial_expert 或 medical_expert）的專業人格與輸出規範。

雲端環境自適應：針對 Railway 部署優化了 yfinance 代號補全、DDGS 區域鎖定與 Docker 絕對路徑處理。

# 🛠️ 功能模組
1. 金融深度研究 (Financial Research)
即時數據：自動校正股票代號（如 2330 -> 2330.TW）並抓取 yfinance 即時行情。

市場情緒：透過 DuckDuckGo API 定位 tw-tzh 區域，過濾掉無關雜訊，精準獲取台股財經新聞。

風險量化：依據 financial_expert 規範進行 1-10 分的風險評估。

2. 醫療知識庫 (Medical RAG)
RAG 知識檢索 (search_device_manual)：針對醫療器材說明書進行 PDF 解析、語意切片與向量化存儲。

生理數據分析(get_user_health_data)：獲取用戶歷史紀錄，對照醫學標準提供衛教建議。

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
# Railway 或 Docker 內部連線
DATABASE_URL=postgresql+psycopg://postgres:密碼@db:5432/postgres
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
金融分析	"分析股票 2330"	自動補全為 2330.TW，抓取股價與新聞，產出格式化投資快報。
私有知識	"Err 3 是什麼意思？"	檢索 PDF，回答「壓脈帶充氣錯誤」並提供排除步驟。
數據分析	"分析我最近的血壓趨勢。"	調用數據工具，對比數值並給予健康判讀。
邊界防禦	"推薦今天的股票。"	觸發 Medical-Expert 規範，禮貌拒絕回答醫療以外問題。
法律免責	(任何建議後)	自動附加「本建議僅供參考，不具醫療診斷效力。」
技能切換	"請啟動 financial_expert"	Agent 讀取 Markdown 規範，行為變更為專業分析師。

# 專案結構

app/services/tools/: 核心工具集（RAG 檢索、數據查詢、技能加載）。

skills/：存放專業領域的 Markdown 指令（如 financial_expert/SKILL.md）。

data/: 存放原始 PDF 醫療器材說明書。

static/：前端介面，包含「官方模式」與「手動模式」的對比頁面。

ingest_pdf.py: 自動化資料清洗、切片與向量化存儲腳本。

docker-compose.yml: 定義服務拓撲與 Named Volumes 持久化配置。