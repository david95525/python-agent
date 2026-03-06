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
