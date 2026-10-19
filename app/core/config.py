"""
Centralized application settings, loaded from environment variables / .env.
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "MF Ventures Equipment Maintenance API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Security ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080

    # --- Database ---
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # --- CORS ---
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # --- File storage ---
    STORAGE_DIR: str = "./storage/attachments"
    MAX_UPLOAD_MB: int = 15

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- First admin bootstrap ---
    FIRST_ADMIN_EMAIL: str = "admin@mfventures.com"
    FIRST_ADMIN_PASSWORD: str = "change-this-password"
    FIRST_ADMIN_FULL_NAME: str = "System Administrator"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
