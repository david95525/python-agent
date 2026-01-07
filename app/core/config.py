from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # 這些名稱必須與 .env 裡的 Key (不分大小寫) 一致
    port: int = 8000
    environment: str = "development"
    active_ai_provider: str = "google"
    
    gemini_api_key: str
    database_url: str

    # 設定讀取 .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# 建立實例
settings = Settings()