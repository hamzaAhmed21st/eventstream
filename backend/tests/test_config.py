from __future__ import annotations

import socket

import pytest
from scripts.prepare_test_database import get_test_database_url

from app.core.config import Settings
from app.db.session import create_database_engine


def test_compose_style_comma_separated_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:5173, https://dashboard.example.test ",
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://dashboard.example.test",
    ]


def test_json_encoded_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["http://localhost:5173", "https://dashboard.example.test"]',
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://dashboard.example.test",
    ]


def test_missing_consumer_name_uses_runtime_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_CONSUMER_NAME", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "eventstream-worker-host")

    settings = Settings(_env_file=None)

    assert settings.redis_consumer_name == "eventstream-worker-host"


@pytest.mark.parametrize("consumer_name", ["", "   "])
def test_blank_consumer_name_uses_runtime_hostname(
    monkeypatch: pytest.MonkeyPatch,
    consumer_name: str,
) -> None:
    monkeypatch.setattr(socket, "gethostname", lambda: "eventstream-worker-host")

    settings = Settings(_env_file=None, redis_consumer_name=consumer_name)

    assert settings.redis_consumer_name == "eventstream-worker-host"


def test_explicit_consumer_name_is_trimmed() -> None:
    settings = Settings(_env_file=None, redis_consumer_name="  worker-a  ")

    assert settings.redis_consumer_name == "worker-a"


async def test_database_engine_hides_statement_parameters() -> None:
    engine = create_database_engine(
        "postgresql+psycopg://eventstream:distinctive-password@localhost/eventstream"
    )
    try:
        assert engine.sync_engine.hide_parameters is True
    finally:
        await engine.dispose()


def test_test_database_helper_uses_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override = "postgresql+psycopg://eventstream:private@localhost/custom_test"
    monkeypatch.setenv("TEST_DATABASE_URL", override)

    assert get_test_database_url() == override
