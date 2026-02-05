import os
import json
from sqlalchemy import text
from langchain.tools import tool
from app.core.config import settings
from app.utils.logger import setup_logger

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
            model="models/text-embedding-004",
            google_api_key=settings.gemini_api_key)
    elif provider == "openai":
        return OpenAIEmbeddings(model="text-embedding-3-small")
    elif provider == "bedrock":
        return BedrockEmbeddings(region_name=os.getenv("AWS_REGION",
                                                       "us-east-1"),
                                 model_id="amazon.titan-embed-text-v2:0")
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
            connection=settings.database_url,
            collection_name=collection_name,
        )

        logger.info(
            f"🔍 [RAG] 執行檢索. Original: {query} | Augmented: {search_query}")

        # 診斷數據庫連線與筆數
        with vector_store.session_maker() as session:
            count_query = text("""
                SELECT count(*) FROM langchain_pg_embedding 
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
            """)
            count = session.execute(count_query, {
                "name": collection_name
            }).scalar()
            logger.debug(
                f"[DB Check] Collection '{collection_name}' 總筆數: {count}")

        # 執行檢索
        docs = vector_store.similarity_search(search_query, k=8)

        if not docs:
            logger.warning(f"[RAG] 檢索結果為空！Query: {search_query}")
            return "說明書中目前查無此內容，請諮詢客服。"

        # 記錄抓到的片段摘要 (DEBUG 模式下可見)
        logger.debug(f"[RAG] 命中 {len(docs)} 個片段")
        for i, doc in enumerate(docs[:3]):
            clean_snippet = doc.page_content[:100].replace('\n', ' ')
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
    bp_history = [{
        "date": "2025-01-05",
        "sys": 118,
        "dia": 78,
        "pul": 72
    }, {
        "date": "2025-01-20",
        "sys": 122,
        "dia": 80,
        "pul": 75
    }, {
        "date": "2025-02-12",
        "sys": 125,
        "dia": 82,
        "pul": 68
    }, {
        "date": "2025-02-25",
        "sys": 120,
        "dia": 79,
        "pul": 70
    }, {
        "date": "2025-03-08",
        "sys": 119,
        "dia": 77,
        "pul": 74
    }, {
        "date": "2025-03-22",
        "sys": 121,
        "dia": 81,
        "pul": 71
    }, {
        "date": "2025-04-10",
        "sys": 124,
        "dia": 83,
        "pul": 73
    }, {
        "date": "2025-04-28",
        "sys": 118,
        "dia": 76,
        "pul": 69
    }, {
        "date": "2025-05-15",
        "sys": 117,
        "dia": 75,
        "pul": 72
    }, {
        "date": "2025-05-30",
        "sys": 120,
        "dia": 78,
        "pul": 76
    }, {
        "date": "2025-06-11",
        "sys": 122,
        "dia": 80,
        "pul": 70
    }, {
        "date": "2025-06-25",
        "sys": 126,
        "dia": 84,
        "pul": 74
    }, {
        "date": "2025-07-04",
        "sys": 123,
        "dia": 81,
        "pul": 75
    }, {
        "date": "2025-07-19",
        "sys": 121,
        "dia": 79,
        "pul": 72
    }, {
        "date": "2025-08-05",
        "sys": 119,
        "dia": 78,
        "pul": 71
    }, {
        "date": "2025-08-20",
        "sys": 120,
        "dia": 80,
        "pul": 73
    }, {
        "date": "2025-09-12",
        "sys": 122,
        "dia": 82,
        "pul": 68
    }, {
        "date": "2025-09-28",
        "sys": 118,
        "dia": 77,
        "pul": 70
    }, {
        "date": "2025-10-03",
        "sys": 125,
        "dia": 85,
        "pul": 77
    }, {
        "date": "2025-10-21",
        "sys": 121,
        "dia": 80,
        "pul": 74
    }, {
        "date": "2025-11-09",
        "sys": 123,
        "dia": 81,
        "pul": 72
    }, {
        "date": "2025-11-24",
        "sys": 119,
        "dia": 78,
        "pul": 70
    }, {
        "date": "2025-12-10",
        "sys": 126,
        "dia": 83,
        "pul": 75
    }, {
        "date": "2025-12-25",
        "sys": 122,
        "dia": 80,
        "pul": 71
    }]

    result = {"status": "success", "userId": user_id, "history": bp_history}
    logger.debug(f"[HealthData] 成功獲取 {len(bp_history)} 筆歷史紀錄")
    return json.dumps(result, ensure_ascii=False)
