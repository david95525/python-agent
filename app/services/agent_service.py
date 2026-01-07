from typing import List, Dict
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from app.services.providers.google import GoogleProvider
from app.core.config import settings
# from app.services.providers.aws import AWSBedrockProvider # 未來擴充

class AgentService:
    def __init__(self):
        # 1. 初始化資源 (這裡建議之後可以用 DI 注入)
        self.api_key = settings.gemini_api_key
        self.db_url = settings.database_url
        
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=self.api_key
        )
        
        # 2. 選擇 Provider (這裡可以根據 .env 動態切換)
        self.provider = GoogleProvider(api_key=self.api_key)
        
        # 3. 簡單記憶體 (生產環境建議改用 Redis 或 DB)
        self.chat_history_map: Dict[str, List[Dict]] = {}

    async def handle_chat(self, user_id: str, message: str) -> str:
        # A. 取得歷史紀錄
        history = self.chat_history_map.get(user_id, [])

        # B. RAG：檢索向量資料庫
        context = await self._get_vector_context(message)
        # C. 呼叫 Provider 取得回應
        # 注意：我們把 Prompt 組合邏輯也封裝在裡面，或在這裡組合後傳入
        try:
            final_text = await self.provider.generate_response(
                message=message,
                context=context,
                history=history
            )

            # D. 更新記憶體 (只存對話，不存檢索到的 Context 以節省 Token)
            self._update_history(user_id, message, final_text)
            
            return final_text
        except Exception as e:
            print(f"Service Error: {e}")
            return "系統暫時無法回應，請稍後再試。"

    async def _get_vector_context(self, message: str) -> str:
        """封裝 RAG 檢索邏輯"""
        try:
            vector_store = PGVector(
                embeddings=self.embeddings,
                connection=self.db_url,
                collection_name="bp_docs_gemini",
                use_jsonb=True,
            )
            # --- 診斷診斷日誌開始 ---
            # 取得底層 Session 並計算該 collection 的總筆數
            with vector_store.session_maker() as session:
                from sqlalchemy import text
                # 查詢該 collection 目前有多少筆 embedding
                count_query = text("""
                    SELECT count(*) FROM langchain_pg_embedding 
                    WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :name)
                """)
                count = session.execute(count_query, {"name": "bp_docs_gemini"}).scalar()
                print(f"📊 [DB Check] Collection 'bp_docs_gemini' 目前總共有 {count} 筆向量資料")
                
            docs = vector_store.similarity_search(message, k=3)
            return "\n\n".join([doc.page_content for doc in docs]) if docs else ""
        except Exception as e:
            print(f"Vector Search Error: {e}")
            return ""

    def _update_history(self, user_id: str, user_msg: str, ai_msg: str):
        history = self.chat_history_map.get(user_id, [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_msg})
        self.chat_history_map[user_id] = history[-10:] # 只保留最近 5 輪對話