from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Mapping
from contextlib import suppress
from typing import NoReturn, Protocol, cast

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.protocols import RedisClient, RedisFields, RedisScalar
from app.db.session import create_database_engine, create_session_factory
from app.schemas.events import StreamEnvelope
from app.services.persistence import EventPersistenceService, PersistenceOutcome

logger = logging.getLogger(__name__)


class EventPersister(Protocol):
    async def persist(self, envelope: StreamEnvelope) -> PersistenceOutcome: ...


class EventWorker:
    def __init__(
        self,
        redis: RedisClient,
        persistence: EventPersister,
        settings: Settings,
    ) -> None:
        self._redis = redis
        self._persistence = persistence
        self._settings = settings

    async def ensure_consumer_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                self._settings.redis_stream,
                self._settings.redis_consumer_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        else:
            logger.info(
                "Created Redis Stream consumer group",
                extra={
                    "event_name": "worker.group.created",
                    "stream": self._settings.redis_stream,
                    "consumer_group": self._settings.redis_consumer_group,
                },
            )

    async def run(self, stop_event: asyncio.Event) -> None:
        await self.ensure_consumer_group()
        logger.info(
            "Worker started",
            extra={
                "event_name": "worker.started",
                "stream": self._settings.redis_stream,
                "consumer_group": self._settings.redis_consumer_group,
                "consumer": self._settings.redis_consumer_name,
            },
        )
        while not stop_event.is_set():
            try:
                batches = await self._redis.xreadgroup(
                    self._settings.redis_consumer_group,
                    self._settings.redis_consumer_name,
                    {self._settings.redis_stream: ">"},
                    count=self._settings.redis_batch_size,
                    block=self._settings.redis_block_ms,
                )
            except RedisError:
                logger.exception(
                    "Redis Stream read failed",
                    extra={"event_name": "worker.read.failed"},
                )
                await _wait_or_stop(stop_event, 1.0)
                continue

            for _, messages in batches:
                for message_id, fields in messages:
                    await self.process_message(message_id, fields)

        logger.info("Worker stopped", extra={"event_name": "worker.stopped"})

    async def process_message(self, message_id: RedisScalar, fields: RedisFields) -> None:
        display_message_id = _decode(message_id)
        try:
            envelope = _parse_envelope(fields)
        except (KeyError, UnicodeDecodeError, ValidationError):
            logger.exception(
                "Invalid Redis Stream payload left pending",
                extra={
                    "event_name": "worker.message.invalid",
                    "stream_message_id": display_message_id,
                },
            )
            return

        try:
            outcome = await self._persistence.persist(envelope)
        except SQLAlchemyError:
            logger.exception(
                "Database persistence failed; message remains pending",
                extra={
                    "event_name": "worker.message.persistence_failed",
                    "stream_message_id": display_message_id,
                    "event_id": str(envelope.event.event_id),
                },
            )
            return

        try:
            acknowledged_count = await self._redis.xack(
                self._settings.redis_stream,
                self._settings.redis_consumer_group,
                message_id,
            )
        except RedisError:
            logger.exception(
                "Redis acknowledgement failed after safe database outcome",
                extra={
                    "event_name": "worker.message.ack_failed",
                    "stream_message_id": display_message_id,
                    "event_id": str(envelope.event.event_id),
                    "persistence_outcome": outcome.value,
                },
            )
            return

        if acknowledged_count != 1:
            logger.warning(
                "Redis did not acknowledge the expected pending message",
                extra={
                    "event_name": "worker.message.ack_missing",
                    "stream_message_id": display_message_id,
                    "event_id": str(envelope.event.event_id),
                    "persistence_outcome": outcome.value,
                    "acknowledged_count": acknowledged_count,
                },
            )
            return

        logger.info(
            "Metric event safely processed and acknowledged",
            extra={
                "event_name": "worker.message.acknowledged",
                "stream_message_id": display_message_id,
                "event_id": str(envelope.event.event_id),
                "persistence_outcome": outcome.value,
            },
        )


def _parse_envelope(fields: Mapping[RedisScalar, RedisScalar]) -> StreamEnvelope:
    raw_data = fields.get("data", fields.get(b"data"))
    if raw_data is None:
        raise KeyError("data")
    return StreamEnvelope.model_validate_json(_decode(raw_data))


def _decode(value: RedisScalar) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


async def _wait_or_stop(stop_event: asyncio.Event, wait_seconds: float) -> None:
    with suppress(TimeoutError):
        async with asyncio.timeout(wait_seconds):
            await stop_event.wait()


async def run_worker(settings: Settings) -> None:
    engine = create_database_engine(settings.database_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    persistence = EventPersistenceService(create_session_factory(engine))
    worker = EventWorker(cast(RedisClient, redis), persistence, settings)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(shutdown_signal, stop_event.set)

    try:
        await worker.run(stop_event)
    finally:
        await redis.aclose()
        await engine.dispose()


def main() -> NoReturn:
    settings = get_settings()
    configure_logging(settings.log_level)
    with suppress(KeyboardInterrupt):
        asyncio.run(run_worker(settings))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
