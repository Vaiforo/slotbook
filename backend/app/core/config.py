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

    broker_url: str = "amqp://slotbook:slotbook_local_only@127.0.0.1:5672//"
    email_url: str | None = None
    email_api_key: str | None = None
    notification_max_attempts: int = Field(default=5, ge=1, le=20)

    ai_model: str | None = None
    ai_api_key: str | None = None
    ai_url: str = "https://api.openai.com/v1/chat/completions"
    ai_timeout_seconds: float = Field(default=8, ge=1, le=15)
    ai_daily_request_limit: int = Field(default=100, ge=1, le=10000)
    ai_limit: int = Field(default=5, ge=1, le=100)

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
        if self.ai_model or self.ai_api_key:
            if not self.ai_model or not self.ai_api_key or not self.redis_url:
                raise ValueError("AI requires ai_model, ai_api_key and redis_url")
            ai_url = urlsplit(self.ai_url)
            if (
                ai_url.scheme != "https"
                or not ai_url.hostname
                or ai_url.username
                or ai_url.password
                or ai_url.query
                or ai_url.fragment
            ):
                raise ValueError("ai_url must be an HTTPS URL without credentials or query")
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
