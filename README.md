# Agent-Research: AI Deep Research Platform (Finance & Medical)

基於 FastAPI + Gemini 2.5 Flash + LangGraph 的自主代理平台
本專案是一個集成了 DeepAgents (官方自主代理) 與 LangGraph (自定義思考鏈) 的先進 AI 系統。它不僅能處理醫療知識庫查詢與生理數據分析，還能針對金融標的進行即時深度研究。

# 🚀 核心進化與技術亮點

- **雙模式研究架構**：
  - **官方模式 (Official DeepAgents)**：利用 Gemini 的原生 Tool Calling 進行自主規劃與工具調用。
  - **手動模式 (Manual LangGraph)**：透過顯式定義「研究-風險分析-決策」節點，實現可控且透明的思考鏈（金融研究專用）。
- **醫療思考鏈 (Medical Workflow)**：採用 LangGraph 構建，包含意圖路由 (Router)、數據抓取 (Fetch)、健康分析 (Analyst) 與動態視覺化 (Visualizer) 節點。
- **動態技能注入 (Skill Injection)**：透過工具 `load_specialized_skill` 讀取 `skills/{skill_name}/SKILL.md`，動態賦予 Agent 不同領域（如：financial_expert 或 health_analyst）的專業人格與輸出規範。
- **混合持久化機制**：
  - **SQLite (AsyncSqliteSaver)**：負責 LangGraph 的狀態保存與對話記憶 (Thread-based Memory)。
  - **PostgreSQL (pgvector)**：專用於 RAG (檢索增強生成)，存儲 PDF 說明書的向量數據（由 `ingest_pdf.py` 處理）。

# 🧩 技術實現詳解 (Technical Deep Dive)

本專案的核心競爭力在於高度可控的 AI 思考鏈與透明的執行過程。以下是關鍵功能的技術實現路徑：

### 1. 意圖路由與分流機制 (Routing & Branching)
系統不再使用傳統的 if-else 硬編碼流轉，而是完全由 LLM 的判定結果驅動：
*   **初始意圖判定**: 在 `app/services/medical/nodes/router.py` 的 `node_router` 中，利用 `structured_output` 取得 `intent`，並透過 `Command(goto=destination)` 實現非線性的節點跳轉。
*   **純查詢早停 (Early Termination)**: 
    *   **核心代碼**: `app/services/medical/nodes/analyst.py` -> `node_fetch_health_records()`
    *   **邏輯**: 當 `intent == "health_query"` 時，回傳 `Command(goto=END)`。這會讓 Graph 在抓取完數據後立即終止執行，避免進入後續需要消耗 LLM Token 的 `health_analyst` 分析節點。
*   **安全性與快取攔截**: 在 `node_router` 中，設有重複輸入快取機制，若偵測到重複輸入則直接沿用前次意圖。同時，若偵測到繪圖確認意圖，也會直接跳轉至 `visualizer` 節點。

### 2. 人機協作中斷與狀態恢復 (Human-in-the-loop)
*   **實作位置**: `app/services/medical/service.py` -> `node_check_date_wrapper()`
*   **機制**: 使用 LangGraph 的 `interrupt()` 暫停當前 Task 並保存線程狀態（Thread State）。當使用者補齊資料（如：日期）後，透過 `Command(resume=input)` 恢復執行，並由 `Command(goto="router")` 引導回流至起點重新解析。

### 3. SSE 串流與即時流程圖渲染 (Real-time Visualization)
*   **後端監聽**: `app/services/medical/service.py` -> `handle_chat()`
    *   利用 `app.astream_events(..., version="v2")` 監聽 `on_chain_start` 與 `on_chain_end`。
    *   每當節點開始執行，即 `yield` 一個 `type: "graph"` 的 JSON 事件，包含最新的 Mermaid Code 與 `node_name`。
*   **前端渲染**: `static/js/chat.js` -> `renderGraph()`
    *   前端收到圖表事件後，會在 Mermaid 原始碼末端注入 `class {node} activeNode` 樣式代碼。
    *   調用 `mermaid.run()` 進行渲染，達成畫面上節點隨執行進度「跳轉高亮」的視覺效果。

### 4. 領域技能注入 (Skill Injection)
*   **實作位置**: `app/utils/registry_loader.py` 與 `app/services/tools/system_tools.py`
*   **機制**: 系統會從 `skills/` 目錄讀取對應的 `SKILL.md`（如金融專家、健康分析師），並將其內容作為 System Prompt 的一部分動態注入 LLM。這使得同一套 Graph 節點能根據當前意圖展現出完全不同的專業深度與行為規範。

# 🛠️ 功能模組

### 1. 金融深度研究 (Financial Research)
- **即時數據**：自動校正股票代號（如 2330 -> 2330.TW）並抓取 yfinance 即時行情。
- **市場情緒**：透過 DuckDuckGo API 定位 tw-tzh 區域，獲取台股最新財經新聞。
- **深度分析**：手動模式下會歷經「數據採集 -> 專家解讀 -> 風險評估」的完整鏈條。

### 2. 醫療健康助理 (Medical AI)
- **設備知識檢索 (get_device_knowledge)**：目前透過模擬知識庫 (Mock KB) 針對 Microlife 醫療器材（血壓計、耳溫槍等）的錯誤代碼 (Err) 與故障排除流程進行匹配。
- **健康數據分析 (get_user_health_data)**：從遠端 API 獲取用戶歷史血壓與心率，並對照醫學標準提供趨勢分析。
- **緊急狀態識別**：若偵測到危險血壓值 (≥160/100)，系統會自動觸發 `[EMERGENCY]` 標記並給予急救指引。
- **動態視覺化 (plot_health_chart)**：自動將健康數據轉化為專業圖表（折線圖、長條圖、散佈圖）。
- **RAG 預研 (search_device_manual)**：已具備 PDF 向量化腳本 `ingest_pdf.py`，支援未來切換至完全動態的知識庫檢索。

# 快速開始

1. **環境準備**
   建立 `.env` 檔案並設定以下變數：
   ```env
   PORT=8000
   ENVIRONMENT=production
   GEMINI_API_KEY=你的Gemini金鑰
   # PostgreSQL 用於 pgvector (RAG 存儲)
   DATABASE_URL=postgresql+psycopg://postgres:密碼@db:5432/postgres
   # 遠端健康數據 API
   EXTERNAL_API_URL=https://api.example.com
   # 伺服器網域 (用於安全性檢查)
   APP_DOMAIN=your-agent-lab.com
   # 本伺服器存取密碼 (由前端或外部調用時使用)
   APP_AUTH_TOKEN=your_secure_token
   ```

2. **使用 Docker Compose 一鍵部署 (推薦)**
   ```bash
   # 建置鏡像並啟動服務
   docker compose up -d --build

   # (選配) 導入 PDF 資料至 PostgreSQL (pgvector)
   docker compose exec agent python ingest_pdf.py
   ```

3. **開發環境執行**
   ```bash
   # 安裝依賴
   uv sync

   # 啟動開發伺服器
   uv run fastapi dev main.py --host 0.0.0.0
   ```

# 📝 測試案例

| 測試場景 | 詢問範例 | 預期 Agent 行為 |
| :--- | :--- | :--- |
| **金融分析** | "分析股票 2330" | 自動補全代號，抓取股價與新聞，產出格式化投資快報。 |
| **設備故障** | "Err 3 是什麼意思？" | 識別為 device_expert，回答「袖帶充氣異常」並提供步驟。 |
| **數據趨勢** | "幫我分析最近的血壓" | 調用 API 抓取數據，給予趨勢總結。 |
| **動態繪圖** | "幫我畫出血壓圖表" | 解析日期範圍，調用繪圖工具產生 Base64 趨勢圖。 |
| **緊急攔截** | (數據異常時) | 自動觸發 `[EMERGENCY]` 邏輯，提示立即就醫。 |

# 專案結構

- `app/services/medical/nodes/`：LangGraph 核心節點（Router, Analyst, Expert...）。
- `app/services/tools/`：核心工具集（金融、醫療、系統工具）。
- `skills/`：存放專業領域的 Markdown 規範（人格設定）。
- `static/`：多功能前端介面（包含測試、Demo、研究區）。
- `ingest_pdf.py`：PDF 向量化存儲至 PostgreSQL 的腳本。

# 🛠️ 如何執行單元測試
本專案提供自動化測試，驗證 AI 節點邏輯（不產生 API 費用）：
- 指令行：輸入 `pytest tests/unit/test_nodes.py`。
- 檢查重點：`test_router_logic` (路由精準度)、`test_health_analyst_emergency` (緊急攔截機制)。
