import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    openai_api_version: str
    azure_openai_chat_deployment_name: str

    # Azure OpenAI Embeddings
    azure_openai_embedding_deployment_name: str = ""

    # Database
    database_path: str = "database.db"
    database_url: str = ""

    # Azure Storage
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Pipeline
    token_alert_threshold: int = 80000
    llm_temperature: float = 0.1

    # App
    app_title: str = "AI Interview Feedback Pipeline Server"
    app_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()