from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    port: int = 8000
    environment: str = "development"
    active_ai_provider: str = "google"
    api_domain: str
    api_token: str
    gemini_api_key: str
    database_url: str

    # LangChain / LangSmith Tracing
    langsmith_tracing: str = "false"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str | None = None
    langsmith_project: str = "Agent-Research"

    def setup_tracing(self):
        """將 LangSmith 設定注入 os.environ 以供 LangChain 自動讀取"""
        if self.langsmith_tracing.lower() == "true":
            # LangChain SDK 核心仍主要讀取這些環境變數
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_ENDPOINT"] = self.langsmith_endpoint
            os.environ["LANGCHAIN_PROJECT"] = self.langsmith_project
            if self.langsmith_api_key:
                os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            
            # 同時注入 LANGSMITH_ 前綴以確保相容性
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_ENDPOINT"] = self.langsmith_endpoint
            os.environ["LANGSMITH_API_KEY"] = self.langsmith_api_key or ""
            os.environ["LANGSMITH_PROJECT"] = self.langsmith_project

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            # 將 postgres:// 替換為 postgresql+psycopg:// (針對 psycopg3)
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
