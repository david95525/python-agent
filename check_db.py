import asyncio
from langchain_postgres.vectorstores import PGVector
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings
from sqlalchemy import text


async def dump_all_vectors():
    print("🚀 開始讀取向量資料庫全部內容...")

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=settings.gemini_api_key)

    try:
        vector_store = PGVector(
            embeddings=embeddings,
            connection=settings.database_url,
            collection_name="bp_docs_gemini",
        )

        # 1. 先確認總筆數與內容
        with vector_store.session_maker() as session:
            # 直接從 raw table 撈出所有原始文字
            query = text("""
                SELECT document FROM langchain_pg_embedding 
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
            """)
            results = session.execute(query, {
                "name": "bp_docs_gemini"
            }).fetchall()

            print(f"📊 總筆數: {len(results)}")
            print("-" * 50)

            for i, row in enumerate(results):
                content = row[0]
                print(f"【Chunk {i+1}】")
                print(content[:300])  # 每筆印出前 300 字
                print("-" * 50)

    except Exception as e:
        print(f"❌ 讀取失敗: {e}")


if __name__ == "__main__":
    asyncio.run(dump_all_vectors())
