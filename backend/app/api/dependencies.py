from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.protocols import RedisClient
from app.services.publisher import EventPublisher
from app.services.queries import EventQueryService


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_redis_client(request: Request) -> RedisClient:
    return cast(RedisClient, request.app.state.redis)


def get_database_engine(request: Request) -> AsyncEngine:
    return cast(AsyncEngine, request.app.state.db_engine)


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.db_session_factory)
    async with factory() as session:
        yield session


def get_event_publisher(
    redis: Annotated[RedisClient, Depends(get_redis_client)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> EventPublisher:
    return EventPublisher(redis, settings.redis_stream)


def get_event_query_service(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> EventQueryService:
    return EventQueryService(session)
