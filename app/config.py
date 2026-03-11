from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "stockmgr"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./stockmgr.db"
    secret_key: str = "change-me-for-production"

    auth_mode: Literal["dev", "oauth", "google", "microsoft"] = "dev"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None

    calendar_provider: Literal["none", "google", "microsoft"] = "none"
    renewal_window_days: int = 30
    admin_emails: str = ""
    excel_api_key: str = ""
    excel_api_user_email: str = ""

    provider_config_path: str = "config/barcode-providers.default.json"
    provider_schema_path: str = "config/barcode-providers.schema.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
