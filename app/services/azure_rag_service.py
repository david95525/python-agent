# app/services/azure_rag_service.py
import os
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.azure import AzureAIChatCompletionClient
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
class AzureRAGService:    
    def __init__(self):
        # 1. 初始化 Azure Search (知識庫)
        self.search_client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT"),
            index_name="microlife-manuals",
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
        )
        
        # 2. 初始化 AutoGen Agent (大腦)
        self.model_client = AzureAIChatCompletionClient(
            model="gpt-4o-mini",
            endpoint="https://models.inference.ai.azure.com",
            credential=AzureKeyCredential(os.getenv("GITHUB_TOKEN"))
        )
        
        self.assistant = AssistantAgent(
            name="microlife_expert",
            model_client=self.model_client,
            system_message="你是一位醫療器材專家，僅根據提供的檢索內容回答問題。"
        )

    def get_context(self, query: str) -> str:
        """從 Azure AI Search 獲取上下文"""
        results = self.search_client.search(search_text=query)
        return "\n\n".join([r['content'] for r in results])

    async def answer_question(self, query: str):
        context = self.get_context(query)
        # 模仿範例中的 Augmented Query 寫法
        prompt = f"上下文資料：\n{context}\n\n使用者問題：{query}"
        
        response = await self.assistant.on_messages(
            [TextMessage(content=prompt, source="user")],
            cancellation_token=CancellationToken(),
        )
        return response.chat_message.content