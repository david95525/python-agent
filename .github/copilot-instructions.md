# Copilot usage guide for python-agent 🔧

## Purpose
- 快速讓 AI 編碼代理 (Copilot/GitHub Actions agent) 立即上手本專案。
- 聚焦在能從程式碼中發現且可立即執行的知識：架構、主要入口、開發/執行流程、以及專案特有規範。

---

## 一眼看懂架構 (大圖)
- API: `main.py` + `app/api/chat_router.py`（FastAPI 路由，單一 `/chat` POST）。
- 服務層: `app/services/agent_service.py`（RAG 檢索、會話記憶、呼叫 Provider）。
- Provider 抽象: `app/services/providers/base.py` → 具體實作 `google.py`（Gemini）/未來可加 Azure。
- RAG 與向量 DB: 使用 `scripts/ingest_pdf.py` 產生 embeddings 並寫入 pgvector（collection 名稱 `bp_docs_gemini`）。
- 設定: `app/core/config.py`（Pydantic `Settings` 從 `.env` 讀取）。

---

## 重要工作流程 & 命令 ✅
- 安裝與同步環境: `uv sync`（本專案使用 `uv` 管理環境，不是 `pip`）。
- 啟動開發伺服器: `uv run fastapi dev main.py` 或直接 `python main.py`（會啟動 uvicorn）。
- 建立 & 啟動 pgvector (Docker):

```powershell
docker volume create pg_vector_data
docker run --name pgvector -e POSTGRES_PASSWORD=<pw> -p 5432:5432 -v pg_vector_data:/var/lib/postgresql/data -d ankane/pgvector
# 啟用向量 extension
docker exec -it pgvector psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

- 匯入 PDF：`uv run python scripts/ingest_pdf.py`（預設讀 `data/bp.pdf`，會寫入 collection `bp_docs_gemini`）。

---

## 專案特有約定與實作細節 🔍
- 環境變數（請參考 `.env` 範例）: **GEMINI_API_KEY**, **DATABASE_URL**, **PORT**, **ENVIRONMENT**（由 `app/core/config.py` 讀取）。
- Provider 模式: 透過 `BaseAIProvider.generate_response` 抽象，現有 `GoogleProvider` 使用 LangChain 風格 `SystemMessage` + `HumanMessage` 串接 Gemini (`ainvoke`)。
- 對話記憶：暫存在 `AgentService.chat_history_map`（process memory，限制最近 10 筆）。生產環境建議改為 Redis 或 DB。請在修改時留意 sync/持久化策略。
- RAG 行為: `AgentService._get_vector_context` 使用 `PGVector.similarity_search(..., k=3)` 並回傳合併字串做為 context；collection 名稱硬編為 `bp_docs_gemini`。
- 錯誤與診斷：程式中以 `print()` 做簡易日誌（例如 collection count 查詢），可擴充為 logging 模組或 observability 工具。

---

## 寫 code 的具體指引（給 AI 代理） ✍️
- 新增 Provider：繼承 `BaseAIProvider` 並實作 `async def generate_response(self, message, context, history)`；在 `AgentService.__init__` 中依 `settings.active_ai_provider` 注入。
- 修改 RAG 行為：若變更 collection 名稱或 embedding model，請同步更新 `scripts/ingest_pdf.py`、`AgentService._get_vector_context` 中的 `collection_name`。
- 測試新功能：可模擬 HTTP POST `POST /chat` 請求（JSON: `{ "message": "...", "userId": "test" }`）來驗證整合流程。
- 確認 async：多數 LLM 與 RAG 呼叫為 async，保持 `await` 並避免在 sync context 阻塞 event loop。

---

## 注意事項 & 風險提示 ⚠️
- 設定安全：API keys 請放在 `.env`（不要上傳到 Git）。
- 生產化：目前記憶使用 process memory，非水平擴充友好；若要橫向擴充，請改用集中式 session store（Redis、DB）。
- Model & Cost：`GoogleGenerativeAIEmbeddings` 與 `ChatGoogleGenerativeAI` 依賴 Gemini API，請留意請求配額與計費。

---

## 快速參考（關鍵檔案）
- `main.py` — FastAPI app、路由註冊、靜態目錄
- `app/api/chat_router.py` — `/chat` API 入口
- `app/services/agent_service.py` — RAG + 會話邏輯
- `app/services/providers/google.py` — Gemini 呼叫範例與 System Prompt
- `scripts/ingest_pdf.py` — PDF => embeddings => pgvector 寫入
- `app/core/config.py` — Pydantic 設定與 env 映射

---

如果你想要，我可以根據你的偏好：
- 把這份檔案轉為更精簡的 Checklist 版（便於 CI agent 檢查）
- 加入範例 Postman/cURL 測試命令

請告訴我有沒有遺漏或需要更詳盡的部分，我會立刻修正。 ✅