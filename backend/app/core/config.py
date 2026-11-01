from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SLOTBOOK_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SlotBook"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: str = "postgresql+psycopg://slotbook:slotbook_local_only@127.0.0.1:5432/slotbook"

    redis_url: str | None = None
    login_limit: int = Field(default=10, ge=1, le=10000)
    booking_limit: int = Field(default=20, ge=1, le=10000)
    rate_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_prefix: str = Field(default="slotbook:rate:v1", min_length=1, max_length=100)

    public_origin: str = "http://127.0.0.1:5173"

    @model_validator(mode="after")
    def validate_origin(self) -> Settings:
        if self.environment == "production" and not self.redis_url:
            raise ValueError("Production requires redis_url")
        url = urlsplit(self.public_origin)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.path
            or url.query
            or url.fragment
        ):
            raise ValueError("public_origin must be an exact HTTP(S) origin without path")
        if url.scheme != "https" and (
            self.environment == "production"
            or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("HTTP is allowed only for non-production loopback")
        return self
