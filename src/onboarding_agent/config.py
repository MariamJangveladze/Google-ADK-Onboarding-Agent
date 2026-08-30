"""Validated runtime configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ONBOARDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    runtime_mode: Literal["local", "live"] = "local"
    default_timezone: str = "Asia/Tbilisi"
    quiet_hours_start: int = Field(default=19, ge=0, le=23)
    quiet_hours_end: int = Field(default=10, ge=0, le=23)
    max_message_characters: int = Field(default=2000, ge=100, le=10000)
    demo_api_token: str = ""
    max_knowledge_file_bytes: int = Field(default=10_000_000, ge=100_000, le=50_000_000)

    database_url: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""
    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash"
    google_application_credentials: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    drive_folder_id: str = ""
    knowledge_cache_seconds: int = Field(default=900, ge=60, le=86400)

    def validate_live(self) -> None:
        required = {
            "database_url": self.database_url,
            "slack_bot_token": self.slack_bot_token,
            "slack_app_token": self.slack_app_token,
            "google_api_key": self.google_api_key,
            "google_application_credentials": self.google_application_credentials,
            "google_cloud_project": self.google_cloud_project,
            "drive_folder_id": self.drive_folder_id,
            "demo_api_token": self.demo_api_token,
        }
        missing = [name for name, value in required.items() if not value]
        if self.runtime_mode == "live" and missing:
            raise ValueError(f"Missing live configuration: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
