import os
import json
import io
import base64
import matplotlib.pyplot as plt
import pandas as pd
from typing import Literal
from sqlalchemy import text
from langchain.tools import tool
from app.core.config import settings
from app.utils.logger import setup_logger
from matplotlib.font_manager import FontProperties, fontManager

# 根據 provider 動態載入
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings
from langchain_postgres.vectorstores import PGVector

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


@tool
async def search_device_manual(query: str) -> str:
    """獲取儀器官方說明書內容的唯一來源。"""
    try:
        provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()
        collection_name = f"docs_{provider}"

        # 優化檢索詞
        search_query = query
        if len(query) < 10 and any(char.isdigit() for char in query):
            search_query = f"血壓計 錯誤代碼 {query} 的意義與排除故障方法"

        vector_store = PGVector(
            embeddings=embeddings,
            connection=settings.sqlalchemy_database_url,
            collection_name=collection_name,
        )

        logger.info(f"🔍 [RAG] 執行檢索. Original: {query} | Augmented: {search_query}")

        # 診斷數據庫連線與筆數
        with vector_store.session_maker() as session:
            count_query = text(
                """
                SELECT count(*) FROM langchain_pg_embedding 
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
            """
            )
            count = session.execute(count_query, {"name": collection_name}).scalar()
            logger.debug(f"[DB Check] Collection '{collection_name}' 總筆數: {count}")

        # 執行檢索
        docs = vector_store.similarity_search(search_query, k=8)

        if not docs:
            logger.warning(f"[RAG] 檢索結果為空！Query: {search_query}")
            return "說明書中目前查無此內容，請諮詢客服。"

        # 記錄抓到的片段摘要 (DEBUG 模式下可見)
        logger.debug(f"[RAG] 命中 {len(docs)} 個片段")
        for i, doc in enumerate(docs[:3]):
            clean_snippet = doc.page_content[:100].replace("\n", " ")
            logger.debug(f"  Rank {i+1} Snippet: {clean_snippet}...")

        return "\n\n".join([doc.page_content for doc in docs])

    except Exception as e:
        logger.error(f"[RAG Error] 檢索失敗: {str(e)}", exc_info=True)
        return f"RAG 查詢失敗: {str(e)}"


@tool
def get_user_health_data(user_id: str) -> str:
    """獲取用戶的歷史血壓與心率數據。"""
    logger.info(f"[HealthData] 讀取用戶健康數據: {user_id}")
    # 模擬數據
    bp_history = [
        {"date": "2025-01-05", "sys": 118, "dia": 78, "pul": 72},
        {"date": "2025-01-20", "sys": 122, "dia": 80, "pul": 75},
        {"date": "2025-02-12", "sys": 125, "dia": 82, "pul": 68},
        {"date": "2025-02-25", "sys": 120, "dia": 79, "pul": 70},
        {"date": "2025-03-08", "sys": 119, "dia": 77, "pul": 74},
        {"date": "2025-03-22", "sys": 121, "dia": 81, "pul": 71},
        {"date": "2025-04-10", "sys": 124, "dia": 83, "pul": 73},
        {"date": "2025-04-28", "sys": 118, "dia": 76, "pul": 69},
        {"date": "2025-05-15", "sys": 117, "dia": 75, "pul": 72},
        {"date": "2025-05-30", "sys": 120, "dia": 78, "pul": 76},
        {"date": "2025-06-11", "sys": 122, "dia": 80, "pul": 70},
        {"date": "2025-06-25", "sys": 126, "dia": 84, "pul": 74},
        {"date": "2025-07-04", "sys": 123, "dia": 81, "pul": 75},
        {"date": "2025-07-19", "sys": 121, "dia": 79, "pul": 72},
        {"date": "2025-08-05", "sys": 119, "dia": 78, "pul": 71},
        {"date": "2025-08-20", "sys": 120, "dia": 80, "pul": 73},
        {"date": "2025-09-12", "sys": 122, "dia": 82, "pul": 68},
        {"date": "2025-09-28", "sys": 118, "dia": 77, "pul": 70},
        {"date": "2025-10-03", "sys": 125, "dia": 85, "pul": 77},
        {"date": "2025-10-21", "sys": 121, "dia": 80, "pul": 74},
        {"date": "2025-11-09", "sys": 123, "dia": 81, "pul": 72},
        {"date": "2025-11-24", "sys": 119, "dia": 78, "pul": 70},
        {"date": "2025-12-10", "sys": 126, "dia": 83, "pul": 75},
        {"date": "2025-12-25", "sys": 122, "dia": 80, "pul": 71},
    ]

    result = {"status": "success", "userId": user_id, "history": bp_history}
    logger.debug(f"[HealthData] 成功獲取 {len(bp_history)} 筆歷史紀錄")
    return json.dumps(result, ensure_ascii=False)


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
):
    """
    當用戶明確要求『繪圖』時調用。
    chart_type: 支援 'line' (折線圖，適合看趨勢), 'bar' (柱狀圖，適合看數值對比), 'scatter' (散佈圖)。
    """
    try:
        # 1. 數據解析與預處理
        raw_json = json.loads(data)
        history = raw_json.get("history", [])
        if not history:
            return "數據量不足，無法生成圖表。"

        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        # 初始化畫布
        plt.figure(figsize=(12, 7), dpi=150)
        plt.style.use("seaborn-v0_8-muted")

        # 根據動態類型繪圖
        if chart_type == "bar":
            # 柱狀圖：適合對比特定日期的數值高低
            bar_width = 0.35
            index = range(len(df))
            plt.bar(
                [i - bar_width / 2 for i in index],
                df["sys"],
                bar_width,
                label="收縮壓 (Sys)",
                color="#e74c3c",
                alpha=0.7,
            )
            plt.bar(
                [i + bar_width / 2 for i in index],
                df["dia"],
                bar_width,
                label="舒張壓 (Dia)",
                color="#3498db",
                alpha=0.7,
            )
            plt.xticks(index, df["date"].dt.strftime("%m-%d"), rotation=45)

        elif chart_type == "scatter":
            # 散佈圖：適合觀察數據點的分佈與離散程度
            plt.scatter(
                df["date"],
                df["sys"],
                s=80,
                c="#e74c3c",
                label="收縮壓 (Sys)",
                edgecolors="white",
                alpha=0.8,
            )
            plt.scatter(
                df["date"],
                df["dia"],
                s=80,
                c="#3498db",
                label="舒張壓 (Dia)",
                edgecolors="white",
                alpha=0.8,
            )

        else:  # 預設 line
            # 折線圖：最適合看長期的波動與趨勢
            plt.plot(
                df["date"],
                df["sys"],
                marker="o",
                linestyle="-",
                linewidth=2,
                color="#e74c3c",
                label="收縮壓 (Sys)",
            )
            plt.plot(
                df["date"],
                df["dia"],
                marker="s",
                linestyle="-",
                linewidth=2,
                color="#3498db",
                label="舒張壓 (Dia)",
            )
            plt.fill_between(df["date"], df["sys"], df["dia"], color="gray", alpha=0.1)

        # 圖表通用設定
        plt.title(title, fontproperties=zh_font, fontsize=20, pad=20)
        plt.xlabel("測量日期", fontproperties=zh_font, fontsize=14)
        plt.ylabel("血壓值 (mmHg)", fontproperties=zh_font, fontsize=14)

        plt.legend(prop=zh_font, loc="upper right", frameon=True)

        # 加入正常值參考線 (120/80)
        plt.axhline(y=120, color="#c0392b", linestyle=":", alpha=0.6)
        plt.axhline(y=80, color="#2980b9", linestyle=":", alpha=0.6)
        # 標註參考線文字
        plt.text(
            df["date"].iloc[0],
            122,
            "收縮壓標準 (120)",
            fontproperties=zh_font,
            color="#c0392b",
            alpha=0.8,
        )
        plt.text(
            df["date"].iloc[0],
            82,
            "舒張壓標準 (80)",
            fontproperties=zh_font,
            color="#2980b9",
            alpha=0.8,
        )
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        # 輸出為 Base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)

        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        return f"data:image/png;base64,{img_base64}"

    except Exception as e:
        return f"圖表生成過程中發生錯誤: {str(e)}"
