from __future__ import annotations

import json
import socket
from functools import lru_cache
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_cors_origins(value: Any) -> Any:
    if isinstance(value, str):
        if value.lstrip().startswith("["):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    return value


CorsOrigins = Annotated[list[str], NoDecode, BeforeValidator(_parse_cors_origins)]


def _runtime_consumer_name() -> str:
    return socket.gethostname().strip() or "eventstream-worker"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "EventStream"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://eventstream:eventstream@localhost:5432/eventstream"
    redis_url: str = "redis://localhost:6379/0"
    redis_stream: str = "eventstream:events"
    redis_consumer_group: str = "eventstream-workers"
    redis_consumer_name: str = Field(default_factory=_runtime_consumer_name)
    redis_block_ms: int = Field(default=5_000, ge=100, le=60_000)
    redis_batch_size: int = Field(default=50, ge=1, le=1_000)
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    cors_origins: CorsOrigins = ["http://localhost:5173"]

    @field_validator("database_url")
    @classmethod
    def require_async_psycopg_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        return value

    @field_validator("redis_stream", "redis_consumer_group")
    @classmethod
    def require_named_redis_resource(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Redis stream and group names cannot be empty")
        return normalized

    @field_validator("redis_consumer_name", mode="before")
    @classmethod
    def default_blank_consumer_name(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return _runtime_consumer_name()
        return value

    @field_validator("redis_consumer_name")
    @classmethod
    def normalize_consumer_name(cls, value: str) -> str:
        return value.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
