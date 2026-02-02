import os
from sqlalchemy import text
from langchain.tools import tool
from app.core.config import settings
import json
# 根據 provider 動態載入
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings
from langchain_postgres.vectorstores import PGVector


def get_active_embeddings():
    """與 ingest.py 保持一致的 Embedding 獲取邏輯"""
    provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()

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


# 初始化目前使用的 Embeddings
embeddings = get_active_embeddings()


@tool
async def search_device_manual(query: str) -> str:
    """
    【重要】當使用者詢問血壓計的錯誤代碼（如 ERR1, ERR2, ERR3, E1 等）、
    故障排除、操作步驟、清洗保養或產品規格時，必須優先調用此工具。
    這是獲取儀器官方說明書內容的唯一來源。
    """
    try:
        # 動態決定 Collection 名稱
        provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()
        collection_name = f"microlife_docs_{provider}"
        #優化檢索詞：如果 query 很短又是代碼，幫它補上上下文，增加向量比對權重
        search_query = query
        if len(query) < 10 and any(char.isdigit() for char in query):
            search_query = f"血壓計 錯誤代碼 {query} 的意義與排除故障方法"
        vector_store = PGVector(
            embeddings=embeddings,
            connection=settings.database_url,
            collection_name=collection_name,
        )
        print(f"🔍 [RAG Debug] Provider: {provider} | Query: {search_query}")
        with vector_store.session_maker() as session:
            count_query = text("""
                SELECT count(*) FROM langchain_pg_embedding 
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
            """)
            count = session.execute(count_query, {
                "name": "bp_docs_gemini"
            }).scalar()
            print(f"📊 [DB Check] 向量庫總筆數: {count}")
        # 執行檢索 (維持 k=8 增加命中率)
        docs = vector_store.similarity_search(search_query, k=8)
        if not docs:
            print("⚠️ [RAG Warning] 資料庫回傳為空！")
            return "說明書中目前查無此錯誤代碼的具體描述，請確認代碼是否輸入正確或諮詢客服。"
        # 診斷：看看抓到了什麼
        print(f"🎯 [RAG Result] 找到了 {len(docs)} 個相關片段：")
        for i, doc in enumerate(docs[:3]):
            # 先處理文字，避開在 f-string 裡使用反斜線
            clean_content = doc.page_content[:100].replace('\n', ' ')
            print(f"  📌 Rank {i+1}: {clean_content}...")
        return "\n\n".join([doc.page_content for doc in docs])

    except Exception as e:
        print(f"❌ [RAG Error] {str(e)}")
        return f"RAG 查詢失敗: {str(e)}"


@tool
def get_user_health_data(user_id: str) -> str:
    """
    獲取用戶的歷史血壓與心率數據。
    當用戶詢問「我的血壓最近怎麼樣？」或「幫我分析去年的趨勢」時調用。
    """
    # 模擬 2025 年的血壓數據庫 (對應你的 Node.js 版本)
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

    # 這裡直接回傳 JSON 字串，Gemini 非常擅長處理這種格式
    return json.dumps(
        {
            "status": "success",
            "userId": user_id,
            "history": bp_history
        },
        ensure_ascii=False)
