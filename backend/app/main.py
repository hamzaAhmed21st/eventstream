from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.errors import validation_exception_handler
from app.core.logging import configure_logging
from app.db.session import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(app_settings.database_url)
        redis = Redis.from_url(app_settings.redis_url, decode_responses=False)
        application.state.db_engine = engine
        application.state.db_session_factory = create_session_factory(engine)
        application.state.redis = redis
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    configure_logging(app_settings.log_level)
    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.exception_handler(RequestValidationError)(validation_exception_handler)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health_router)
    application.include_router(events_router)
    return application


app = create_app()
