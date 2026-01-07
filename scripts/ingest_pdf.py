import os
from dotenv import load_dotenv
# 確保這些路徑正確
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres.vectorstores import PGVector

load_dotenv()

def run_ingest():
    # 確認檔案路徑是否存在
    pdf_path = "data/bp.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ 找不到檔案: {pdf_path}，請確認檔案已放入 data 資料夾")
        return

    try:
        print(f"📂 正在讀取血壓計說明書 ({pdf_path})...")
        loader = PyPDFLoader(pdf_path)
        raw_docs = loader.load()

        print("✂️ 正在進行精細切片...")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        docs = splitter.split_documents(raw_docs)

        print(f"🧠 正在生成向量並存入 pgvector... (總共 {len(docs)} 個段落)")
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=os.getenv("GEMINI_API_KEY")
        )

        # 寫入資料庫
        PGVector.from_documents(
            embedding=embeddings,
            documents=docs,
            collection_name="bp_docs_gemini",
            connection=os.getenv("DATABASE_URL"),
            use_jsonb=True,
        )

        print("✅ 成功！Python 版血壓計知識庫已建立。")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    run_ingest()