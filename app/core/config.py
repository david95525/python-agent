from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import os


class Settings(BaseSettings):
    port: int = 8000
    environment: str = "development"
    active_ai_provider: str = "google"

    gemini_api_key: str
    database_url: str

    # --- 關鍵修正：自動處理 Railway 的資料庫連線字串 ---
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
