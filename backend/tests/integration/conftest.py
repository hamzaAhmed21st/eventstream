from __future__ import annotations

import os

import pytest
from sqlalchemy.engine import URL, make_url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    raw_url = os.getenv("TEST_DATABASE_URL")
    if raw_url is None:
        pytest.skip("TEST_DATABASE_URL is not set; isolated PostgreSQL integration is disabled")

    url = make_url(raw_url)
    _validate_isolated_database(url)
    return raw_url


@pytest.fixture(scope="session")
def test_redis_url() -> str:
    raw_url = os.getenv("TEST_REDIS_URL")
    if raw_url is None:
        pytest.skip("TEST_REDIS_URL is not set; isolated Redis integration is disabled")
    return raw_url


def _validate_isolated_database(url: URL) -> None:
    if url.drivername != "postgresql+psycopg":
        pytest.fail("TEST_DATABASE_URL must use the postgresql+psycopg async driver")
    if url.database is None or "test" not in url.database.lower():
        pytest.fail("TEST_DATABASE_URL database name must contain 'test'")

