import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from sqlalchemy import create_engine, text

# 匯入你的設定檔
from app.core.config import settings

load_dotenv()


def run_ingest():
    pdf_path = "data/bp.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ 找不到檔案: {pdf_path}")
        return

    try:
        # 1. 使用 settings.database_url 清空舊資料
        print("🧹 正在清理舊的向量資料...")
        # 將非同步驅動名替換為同步驅動，以便 sqlalchemy 執行清理任務
        sync_url = settings.database_url.replace("postgresql+psycopg",
                                                 "postgresql")
        engine = create_engine(sync_url)

        with engine.connect() as conn:
            conn.execute(
                text("""
                DELETE FROM langchain_pg_embedding 
                WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
            """), {"name": "bp_docs_gemini"})
            conn.commit()

        print(f"📂 正在讀取血壓計說明書...")
        loader = PyPDFLoader(pdf_path)
        raw_docs = loader.load()

        # 2. 強化切片邏輯（增加 Overlap 解決 ERR3 斷裂問題）
        print("✂️ 正在進行重疊式切片 (Overlap: 200)...")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=200,
            separators=["\n\n", "\n", "。", " "])
        docs = splitter.split_documents(raw_docs)

        print(f"🧠 正在生成向量 (總共 {len(docs)} 個段落)...")
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=settings.gemini_api_key  # 使用 settings
        )

        # 3. 存入資料庫
        PGVector.from_documents(
            embedding=embeddings,
            documents=docs,
            collection_name="bp_docs_gemini",
            connection=settings.database_url,  # 使用 settings
            use_jsonb=True,
        )

        print("✅ 成功！資料庫已重新載入。")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")


if __name__ == "__main__":
    run_ingest()
