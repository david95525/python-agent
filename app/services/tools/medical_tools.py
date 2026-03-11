# app/services/tools/medical_tools.py
import os
import httpx
import json
import io
import base64
import matplotlib.pyplot as plt
import pandas as pd
from typing import Literal, Optional
from sqlalchemy import text
from datetime import datetime, timedelta
from langchain.tools import tool
from matplotlib.font_manager import FontProperties, fontManager
from typing import List, Literal


from app.core.config import settings
from app.utils.logger import setup_logger

# 根據 provider 動態載入
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings

# from langchain_postgres.vectorstores import PGVector

# 初始化 Logger
logger = setup_logger("MedicalTools")


def get_active_embeddings():
    provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()
    logger.debug(f"[Embedding] 正在初始化 Provider: {provider}")

    if provider == "google":
        return GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", google_api_key=settings.gemini_api_key
        )
    elif provider == "openai":
        return OpenAIEmbeddings(model="text-embedding-3-small")
    elif provider == "bedrock":
        return BedrockEmbeddings(
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            model_id="amazon.titan-embed-text-v2:0",
        )
    else:
        raise ValueError(f"不支援的 Provider: {provider}")


embeddings = get_active_embeddings()


# @tool
# --- 原先的 RAG 函數已停用 (保留供未來參考) ---
# async def search_device_manual(query: str) -> str:
#     """獲取儀器官方說明書內容"""
#     try:
#         provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()
#         collection_name = f"docs_{provider}"

#         # 優化檢索詞
#         search_query = query
#         if len(query) < 10 and any(char.isdigit() for char in query):
#             search_query = f"血壓計 錯誤代碼 {query} 的意義與排除故障方法"

#         vector_store = PGVector(
#             embeddings=embeddings,
#             connection=settings.sqlalchemy_database_url,
#             collection_name=collection_name,
#         )

#         logger.info(f"🔍 [RAG] 執行檢索. Original: {query} | Augmented: {search_query}")

#         # 診斷數據庫連線與筆數
#         with vector_store.session_maker() as session:
#             count_query = text(
#                 """
#                 SELECT count(*) FROM langchain_pg_embedding
#                 WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
#             """
#             )
#             count = session.execute(count_query, {"name": collection_name}).scalar()
#             logger.debug(f"[DB Check] Collection '{collection_name}' 總筆數: {count}")

#         # 執行檢索
#         docs = vector_store.similarity_search(search_query, k=8)

#         if not docs:
#             logger.warning(f"[RAG] 檢索結果為空！Query: {search_query}")
#             return "說明書中目前查無此內容，請諮詢客服。"

#         # 記錄抓到的片段摘要 (DEBUG 模式下可見)
#         logger.debug(f"[RAG] 命中 {len(docs)} 個片段")
#         for i, doc in enumerate(docs[:3]):
#             clean_snippet = doc.page_content[:100].replace("\n", " ")
#             logger.debug(f"  Rank {i+1} Snippet: {clean_snippet}...")

#         return "\n\n".join([doc.page_content for doc in docs])

#     except Exception as e:
#         logger.error(f"[RAG Error] 檢索失敗: {str(e)}", exc_info=True)
#         return f"RAG 查詢失敗: {str(e)}"


@tool
# 模擬資料functiom
async def get_device_knowledge(query: str) -> str:
    """
    獲取 Microlife 儀器（如血壓計、耳溫槍）的官方說明書、錯誤代碼 (Err) 與排除故障方法。
    這是關於設備硬體操作、電池更換、維護與技術規格的唯一權威來源。
    """
    logger.info(f"🔍 [Knowledge Base] 收到設備查詢: {query}")

    # 模擬設備知識庫 (建議之後可移至 data/manual_kb.json)
    MOCK_KB = {
        "err1": "【錯誤代碼 Err 1】：信號太弱。原因：感測不到脈搏。處理：重新綁緊袖帶，保持手臂靜止並對準心臟位置。",
        "err2": "【錯誤代碼 Err 2】：錯誤信號。原因：測量時受干擾（如說話、移動）。處理：靜坐 5 分鐘後重新測量。",
        "err3": "【錯誤代碼 Err 3】：袖帶壓力異常。原因：袖帶未正確充氣。處理：檢查袖帶是否破損或漏氣，確保插頭接穩。",
        "err5": "【錯誤代碼 Err 5】：結果異常。原因：測量環境不穩定。處理：請確認袖帶綁法，重新開機後再測。",
        "hi_lo": "【顯示 HI / LO】：脈搏或壓力超出測量範疇。HI 代表過高，LO 代表過低。請確認操作流程是否正確。",
        "battery": "【電池符號】：電量不足。請立即更換四顆全新的 1.5V AA 鹼性電池，切勿混用新舊電池。",
        "afib": "【AFIB 圖示】：心房顫動偵測。這是 Microlife 專利技術，若此圖示連續出現三次以上，建議諮詢專業醫師。",
    }

    # 簡單模擬檢索邏輯：尋找 query 中的關鍵字
    query_lower = query.lower()
    results = []

    # 針對 Err 關鍵字做特殊優化
    import re

    err_match = re.search(r"err\s*(\d+)", query_lower)
    if err_match:
        err_key = f"err{err_match.group(1)}"
        if err_key in MOCK_KB:
            results.append(MOCK_KB[err_key])

    # 一般關鍵字比對
    keywords = ["battery", "電池", "afib", "心房", "袖帶", "hi", "lo"]
    for k in keywords:
        if k in query_lower:
            # 找到對應內容 (這裡簡化處理)
            for key, content in MOCK_KB.items():
                if k in key or k in content:
                    if content not in results:
                        results.append(content)

    if not results:
        return "抱歉，目前在說明書中找不到關於此問題的具體說明。建議您確保代碼輸入正確，或聯絡 Microlife 售後服務。"

    return "\n\n".join(results)


@tool
async def get_user_health_data(
    user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None
) -> str:
    """
    從遠端 API 獲取用戶的歷史血壓與心率數據。

    Args:
        user_id: 用戶唯一識別碼。
        start_date: (選填) 查詢起始日期，格式為 yyyy-mm-dd。若未提供，預設為一年前。
        end_date: (選填) 查詢結束日期，格式為 yyyy-mm-dd。若未提供，預設為今天。
    """
    logger.info(
        f"[API Fetch] 正在獲取用戶數據: {user_id}, 範圍: {start_date} 至 {end_date}"
    )

    # 動態處理日期邏輯
    # 如果使用者沒說 end_date，預設為今天
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # 如果使用者沒說 start_date，預設為 end_date 的一年前
    if not start_date:
        # 先解析 end_date 以確保基準點一致
        base_date = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (base_date - timedelta(days=365)).strftime("%Y-%m-%d")

    # 準備 API 請求
    api_url = f"{settings.api_domain}/api/get_bpm_history_data"
    logger.debug(api_url)
    params = {
        "start": start_date,
        "end": end_date,
        "limit": 100,  # 動態查詢時，可以稍微放寬筆數限制
        "offset": 0,
        "time_type": 1,  # 依量測時間搜尋
    }

    headers = {
        "Authorization": f"Bearer {settings.api_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(api_url, headers=headers, params=params)

            if response.status_code != 200:
                logger.error(f"[API Error] 狀態碼: {response.status_code}")
                return json.dumps({"status": "error", "message": "遠端伺服器回應異常"})

            raw_res = response.json()

            # 數據整理
            clean_history = []
            for item in raw_res.get("data", []):
                if item.get("data_type") == "delete" or item.get("sys") == 0:
                    continue
                clean_history.append(
                    {
                        "date": item.get("date"),
                        "sys": item.get("sys"),
                        "dia": item.get("dia"),
                        "pul": item.get("pul"),
                        "note": item.get("note", ""),
                    }
                )

            formatted_data = {
                "status": "success",
                "userId": user_id,
                "range": {
                    "start": start_date,
                    "end": end_date,
                },  # 回傳給 LLM 讓它知道最終查了什麼範圍
                "history": clean_history,
                "total": raw_res.get("total_num", 0),
            }

            logger.info(f"[API Success] 成功解析 {len(clean_history)} 筆量測紀錄")
            logger.debug(f"[Debug] API 原始內容: {formatted_data}")
            return json.dumps(formatted_data, ensure_ascii=False)

    except httpx.RequestError as exc:
        logger.error(f"[API Network Error] 連線失敗: {exc}")
        return json.dumps({"status": "error", "message": "網路連線失敗，無法取得數據"})


DOCKER_FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

try:
    if os.path.exists(DOCKER_FONT_PATH):
        # 優先使用確定的 Docker 路徑
        zh_font = FontProperties(fname=DOCKER_FONT_PATH)
    else:
        # 如果路徑不存在（例如本地開發），則搜尋系統清單
        noto_font = next(
            (f.fname for f in fontManager.ttflist if "Noto Sans CJK" in f.name), None
        )
        if noto_font:
            zh_font = FontProperties(fname=noto_font)
        else:
            # 最後保險：使用預設無襯線字體
            zh_font = FontProperties(family="sans-serif")
except Exception as e:
    print(f"Font loading error: {e}")
    zh_font = FontProperties(family="sans-serif")


@tool
def plot_health_chart(
    data: str,
    title: str = "健康趨勢分析",
    chart_type: Literal["line", "bar", "scatter"] = "line",
    columns: List[str] = ["sys", "dia"],
    labels: List[str] = ["收縮壓", "舒張壓"],
    colors: List[str] = ["#e74c3c", "#3498db"],
    unit: str = "數值",
):
    """
    動態生成健康趨勢圖表。
    columns: 要從數據中提取的 Key (例如 ['weight'] 或 ['sys', 'dia'])
    labels: 對應欄位的中文名稱 (例如 ['體重'] 或 ['收縮壓', '舒張壓'])
    unit: Y 軸的單位標籤 (例如 'kg', 'mmHg', 'mg/dL')
    """
    try:
        #  數據解析
        raw_json = json.loads(data)
        history = raw_json.get("history", [])
        if not history:
            return "數據量不足，無法生成圖表。"

        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        #  畫布初始化
        plt.figure(figsize=(12, 7), dpi=150)
        plt.style.use("seaborn-v0_8-muted")

        #  核心繪圖邏輯：循環處理用戶要求的每一個指標
        for i, col in enumerate(columns):
            if col not in df.columns:
                continue

            label = labels[i] if i < len(labels) else col
            color = colors[i] if i < len(colors) else None

            if chart_type == "bar":
                # 多指標柱狀圖偏移計算
                width = 0.8 / len(columns)
                offset = (i - len(columns) / 2 + 0.5) * width
                plt.bar(
                    range(len(df)),
                    df[col],
                    width,
                    label=label,
                    color=color,
                    alpha=0.7,
                    align="center",
                )
                plt.xticks(range(len(df)), df["date"].dt.strftime("%m-%d"), rotation=45)

            elif chart_type == "scatter":
                plt.scatter(
                    df["date"],
                    df[col],
                    s=80,
                    label=label,
                    color=color,
                    edgecolors="white",
                    alpha=0.8,
                )

            else:  # line
                plt.plot(
                    df["date"],
                    df[col],
                    marker="o",
                    label=label,
                    color=color,
                    linewidth=2,
                )

        #  圖表通用設定 (使用你之前修正的 zh_font)
        plt.title(title, fontproperties=zh_font, fontsize=20, pad=20)
        plt.xlabel("測量日期", fontproperties=zh_font, fontsize=12)
        plt.ylabel(f"{unit}", fontproperties=zh_font, fontsize=12)
        plt.legend(prop=zh_font, loc="upper right")
        plt.grid(True, linestyle="--", alpha=0.5)
        #  特殊參考線 (如果是血壓則保留標準線)
        if "sys" in columns:
            plt.axhline(y=120, color="#c0392b", linestyle=":", alpha=0.5)
        if "dia" in columns:
            plt.axhline(y=80, color="#2980b9", linestyle=":", alpha=0.5)

        plt.tight_layout()

        # 輸出 Base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"

    except Exception as e:
        return f"圖表生成失敗: {str(e)}"


# @tool
# def get_mock_user_health_data(user_id: str) -> str:
#     """獲取用戶的歷史血壓與心率數據。"""
#     logger.info(f"[HealthData] 讀取用戶健康數據: {user_id}")
#     # 模擬數據
#     bp_history = [
#         {"date": "2025-01-05", "sys": 118, "dia": 78, "pul": 72},
#         {"date": "2025-01-20", "sys": 122, "dia": 80, "pul": 75},
#         {"date": "2025-02-12", "sys": 125, "dia": 82, "pul": 68},
#         {"date": "2025-02-25", "sys": 120, "dia": 79, "pul": 70},
#         {"date": "2025-03-08", "sys": 119, "dia": 77, "pul": 74},
#         {"date": "2025-03-22", "sys": 121, "dia": 81, "pul": 71},
#         {"date": "2025-04-10", "sys": 124, "dia": 83, "pul": 73},
#         {"date": "2025-04-28", "sys": 118, "dia": 76, "pul": 69},
#         {"date": "2025-05-15", "sys": 117, "dia": 75, "pul": 72},
#         {"date": "2025-05-30", "sys": 120, "dia": 78, "pul": 76},
#         {"date": "2025-06-11", "sys": 122, "dia": 80, "pul": 70},
#         {"date": "2025-06-25", "sys": 126, "dia": 84, "pul": 74},
#         {"date": "2025-07-04", "sys": 123, "dia": 81, "pul": 75},
#         {"date": "2025-07-19", "sys": 121, "dia": 79, "pul": 72},
#         {"date": "2025-08-05", "sys": 119, "dia": 78, "pul": 71},
#         {"date": "2025-08-20", "sys": 120, "dia": 80, "pul": 73},
#         {"date": "2025-09-12", "sys": 122, "dia": 82, "pul": 68},
#         {"date": "2025-09-28", "sys": 118, "dia": 77, "pul": 70},
#         {"date": "2025-10-03", "sys": 125, "dia": 85, "pul": 77},
#         {"date": "2025-10-21", "sys": 121, "dia": 80, "pul": 74},
#         {"date": "2025-11-09", "sys": 123, "dia": 81, "pul": 72},
#         {"date": "2025-11-24", "sys": 119, "dia": 78, "pul": 70},
#         {"date": "2025-12-10", "sys": 126, "dia": 83, "pul": 75},
#         {"date": "2025-12-25", "sys": 122, "dia": 80, "pul": 71},
#     ]

#     result = {"status": "success", "userId": user_id, "history": bp_history}
#     logger.debug(f"[HealthData] 成功獲取 {len(bp_history)} 筆歷史紀錄")
#     return json.dumps(result, ensure_ascii=False)
