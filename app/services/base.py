from abc import ABC, abstractmethod
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
from app.core.config import settings


class BaseAgent(ABC):

    def __init__(self, service_name: str):
        self.service_name = service_name
        # 初始化 LLM (動態選擇 LLM)
        self.llm = self._get_llm()

    def _get_llm(self):
        """根據環境變數返回對應的 LLM 實例"""
        # 注意：通常 Embedding 與 LLM Provider 會設為同一個，但也可以分開
        provider = os.getenv("LLM_PROVIDER", "google").lower()

        if provider == "google":
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=settings.gemini_api_key,
                temperature=0)
        elif provider == "openai":
            return ChatOpenAI(model="gpt-4o",
                              api_key=os.getenv("OPENAI_API_KEY"),
                              temperature=0)
        elif provider == "bedrock":
            # 未來上 AWS 之後的配置
            return ChatBedrock(
                model_id=
                "anthropic.claude-3-5-sonnet-20240620-v1:0",  # 或 Llama 3
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                model_kwargs={"temperature": 0})
        else:
            raise ValueError(f"不支援的 LLM Provider: {provider}")
