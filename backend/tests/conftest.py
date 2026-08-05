from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://eventstream:eventstream@localhost:5432/eventstream",
        redis_url="redis://localhost:6379/15",
        readiness_timeout_seconds=0.1,
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    yield application
    application.dependency_overrides.clear()

