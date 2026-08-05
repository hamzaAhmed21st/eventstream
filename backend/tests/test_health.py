from __future__ import annotations

from types import TracebackType
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.dependencies import get_database_engine, get_redis_client
from app.core.protocols import RedisClient
from tests.helpers import FakeRedis


class FakeConnection:
    async def execute(self, statement: object) -> None:
        del statement


class FakeConnectionContext:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def __aenter__(self) -> FakeConnection:
        if self.fail:
            raise OSError("test database failure")
        return FakeConnection()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


class FakeEngine:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def connect(self) -> FakeConnectionContext:
        return FakeConnectionContext(fail=self.fail)


def override_health_dependencies(
    app: FastAPI,
    *,
    engine: FakeEngine,
    redis: FakeRedis,
) -> None:
    app.dependency_overrides[get_database_engine] = lambda: cast(AsyncEngine, engine)
    app.dependency_overrides[get_redis_client] = lambda: cast(RedisClient, redis)


def test_liveness_is_process_only(app: FastAPI) -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_succeeds_when_both_dependencies_respond(app: FastAPI) -> None:
    override_health_dependencies(app, engine=FakeEngine(), redis=FakeRedis())

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }


def test_readiness_fails_and_reports_each_unavailable_dependency(app: FastAPI) -> None:
    override_health_dependencies(
        app,
        engine=FakeEngine(fail=True),
        redis=FakeRedis(fail_ping=True),
    )

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable", "redis": "unavailable"},
    }
