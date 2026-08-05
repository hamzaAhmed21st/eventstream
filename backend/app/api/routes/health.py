from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.dependencies import (
    get_app_settings,
    get_database_engine,
    get_redis_client,
)
from app.core.config import Settings
from app.core.protocols import RedisClient

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["alive"]


class DependencyChecks(BaseModel):
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: DependencyChecks


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse(status="alive")


@router.get("/ready", response_model=ReadyResponse)
async def ready(
    response: Response,
    engine: Annotated[AsyncEngine, Depends(get_database_engine)],
    redis: Annotated[RedisClient, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ReadyResponse:
    database_ok, redis_ok = await asyncio.gather(
        _database_is_ready(engine, settings.readiness_timeout_seconds),
        _redis_is_ready(redis, settings.readiness_timeout_seconds),
    )
    is_ready = database_ok and redis_ok
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        checks=DependencyChecks(
            database="ok" if database_ok else "unavailable",
            redis="ok" if redis_ok else "unavailable",
        ),
    )


async def _database_is_ready(engine: AsyncEngine, timeout_seconds: float) -> bool:
    async def check() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        async with asyncio.timeout(timeout_seconds):
            await check()
    except Exception:
        return False
    return True


async def _redis_is_ready(redis: RedisClient, timeout_seconds: float) -> bool:
    try:
        async with asyncio.timeout(timeout_seconds):
            result = await redis.ping()
    except Exception:
        return False
    return bool(result)
