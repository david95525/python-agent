from .base import BaseAIProvider
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


class GoogleProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.2,  # 醫療助手建議降低隨機性，提高穩定度
        )

    async def generate_response(self, message: str, context: str, history: list) -> str:
        # 還原 Node.js 的 System Prompt 邏輯
        system_instruction = (
            f"【參考資料】：\n{context}\n\n"
            "【指令】：請優先根據參考資料回答使用者問題。你是一位專注於醫療器材的助理，"
            "請拒絕回答任何與醫療或血壓計無關的問題。"
        )

        # 轉換歷史紀錄格式 (將 Dict 轉為 LangChain Message 物件)
        # 對標 Node.js 的 contents 陣列
        messages = [SystemMessage(content=system_instruction)]

        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # 加入當前使用者的問題
        messages.append(HumanMessage(content=message))

        # 呼叫 Gemini
        response = await self.llm.ainvoke(messages)
        return response.content
