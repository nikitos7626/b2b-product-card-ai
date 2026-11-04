from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация сервиса."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"

    # Пути проекта (parents[2] от app/core/config.py -> корень репозитория)
    base_dir: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = base_dir / "data"
    output_dir: Path = base_dir / "output"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
