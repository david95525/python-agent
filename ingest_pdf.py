import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres.vectorstores import PGVector
from sqlalchemy import create_engine, text

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings

from app.core.config import settings
from app.utils.logger import setup_logger

# 初始化 Logger
logger = setup_logger("DataIngest")

load_dotenv()


def get_embeddings():
    provider = os.getenv("EMBEDDING_PROVIDER", "google").lower()
    logger.debug(f"[Embedding] 初始化 Provider: {provider}")

    if provider == "google":
        return GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    elif provider == "openai":
        return OpenAIEmbeddings(model="text-embedding-3-small")
    elif provider == "bedrock":
        return BedrockEmbeddings(region_name=os.getenv("AWS_REGION",
                                                       "us-east-1"),
                                 model_id="amazon.titan-embed-text-v2:0")
    else:
        logger.error(f"不支援的 Provider: {provider}")
        raise ValueError(f"不支援的 Provider: {provider}")


def run_ingest():
    pdf_path = "data/bp.pdf"
    provider = os.getenv("EMBEDDING_PROVIDER", "google")
    collection_name = f"docs_{provider}"

    logger.info(f"開始執行資料灌庫程序 (Collection: {collection_name})")

    try:
        # 建立連接與檢查表是否存在
        engine = create_engine(settings.sqlalchemy_database_url)

        logger.info(f"正在檢查並清理舊資料...")
        with engine.connect() as conn:
            # 修改點：加入 IF EXISTS 的檢查，避免第一次運行崩潰
            check_table_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'langchain_pg_embedding'
                );
            """)
            table_exists = conn.execute(check_table_query).scalar()

            if table_exists:
                result = conn.execute(
                    text("""
                    DELETE FROM langchain_pg_embedding 
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
                """), {"name": collection_name})
                conn.commit()
                logger.info(f"✨ 舊資料清理完成，受影響行數: {result.rowcount}")
            else:
                logger.info("ℹ️ 資料表尚未建立，跳過清理步驟。")

                # 載入與切片
        if not os.path.exists(pdf_path):
            logger.error(f"找不到 PDF 檔案: {pdf_path}")
            return

        logger.info(f"📖 正在讀取 PDF: {pdf_path}")
        loader = PyPDFLoader(pdf_path)
        raw_docs = loader.load()
        logger.debug(f"📄 PDF 讀取完成，總頁數: {len(raw_docs)}")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=120,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""])

        docs = splitter.split_documents(raw_docs)
        logger.info(f"切片完成，共產生 {len(docs)} 個文檔片段")
        # Embedding 與 儲存
        embeddings = get_embeddings()
        logger.info(f"正在調用 {provider} API 生成向量並存入資料庫...")

        # PGVector.from_documents 會在底層自動幫你建立表格 (如果不存在的話)
        PGVector.from_documents(
            embedding=embeddings,
            documents=docs,
            collection_name=collection_name,
            connection=settings.sqlalchemy_database_url,
            use_jsonb=True,
        )
        logger.info(f"成功！全數資料已存入 Collection: {collection_name}")

    except Exception as e:
        logger.error(f"灌庫過程中發生致命錯誤: {str(e)}", exc_info=True)


if __name__ == "__main__":
    run_ingest()
