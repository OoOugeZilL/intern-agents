"""Loads runtime settings from environment variables and local defaults."""

from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Stores backend settings used by API, BIRD data, model, and database modules."""

    modelBaseUrl: str = "https://api.deepseek.com"
    modelName: str = "deepseek-chat"
    modelApiKey: str = ""
    birdRawDir: Path = Path("data/bird/raw")
    birdProcessedDir: Path = Path("data/bird/processed")
    birdDemoDir: Path = Path("data/bird/demo")
    birdInstructionsDir: Path = Path("data/bird/instructions")
    databaseUrl: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def LoadSettings():
    """Loads settings from environment variables and .env when present."""
    settings = Settings()
    pairs = {
        "MODEL_BASE_URL": "modelBaseUrl",
        "MODEL_NAME": "modelName",
        "MODEL_API_KEY": "modelApiKey",
        "DATABASE_URL": "databaseUrl",
        "BIRD_RAW_DIR": "birdRawDir",
        "BIRD_PROCESSED_DIR": "birdProcessedDir",
        "BIRD_DEMO_DIR": "birdDemoDir",
    }
    for envName, fieldName in pairs.items():
        if os.getenv(envName): setattr(settings, fieldName, os.getenv(envName))
    return settings
