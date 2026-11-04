import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация сервиса, загружаемая из переменных окружения и .env файла."""
    
    # Провайдер LLM: "auto", "gemini" или "openai"
    llm_provider: str = "auto"
    
    # Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    
    # OpenAI-compatible API
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    
    # Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    output_dir: Path = base_dir / "output"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
