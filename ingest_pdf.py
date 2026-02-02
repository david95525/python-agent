import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres.vectorstores import PGVector
from sqlalchemy import create_engine, text

# 根據需求動態載入不同的 Embedding
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings  # 未來對接 AWS 的關鍵

from app.core.config import settings

load_dotenv()


def get_embeddings():
    """通用 Embedding 選擇器"""
    provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()

    if provider == "google":
        return GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    elif provider == "openai":
        return OpenAIEmbeddings(model="text-embedding-3-small")
    elif provider == "bedrock":
        # 未來遷移到 AWS 時只需改環境變數
        return BedrockEmbeddings(region_name=os.getenv("AWS_REGION",
                                                       "us-east-1"),
                                 model_id="amazon.titan-embed-text-v2:0")
    else:
        raise ValueError(f"不支援的 Provider: {provider}")


def run_ingest():
    pdf_path = "data/bp.pdf"
    provider = os.getenv("EMBEDDING_PROVIDER", "google")
    collection_name = f"microlife_docs_{provider}"

    try:
        # 1. 建立同步連線清理舊資料
        sync_url = settings.database_url.replace("postgresql+psycopg",
                                                 "postgresql")
        engine = create_engine(sync_url)

        print(f"🧹 清理 {collection_name} 中的舊資料...")
        with engine.connect() as conn:
            # 使用更安全的語法清理特定 collection
            conn.execute(
                text("""
                DELETE FROM langchain_pg_embedding 
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
            """), {"name": collection_name})
            conn.commit()

        # 2. 載入與強化切片
        loader = PyPDFLoader(pdf_path)
        raw_docs = loader.load()

        # 針對說明書優化：保持段落完整性
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=120,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""])
        docs = splitter.split_documents(raw_docs)

        # 3. 獲取通用 Embedding 並存入
        embeddings = get_embeddings()
        print(f"🧠 使用 {provider} 生成向量中...")

        PGVector.from_documents(
            embedding=embeddings,
            documents=docs,
            collection_name=collection_name,
            connection=settings.database_url,
            use_jsonb=True,
        )
        print(f"✅ 成功！資料已存入 Collection: {collection_name}")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")


if __name__ == "__main__":
    run_ingest()
