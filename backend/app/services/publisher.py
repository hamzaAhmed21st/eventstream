from __future__ import annotations

from datetime import UTC, datetime

from redis.exceptions import RedisError

from app.core.protocols import RedisClient
from app.schemas.events import EventCreate, StreamEnvelope


class EventPublicationError(RuntimeError):
    pass


class EventPublisher:
    def __init__(self, redis: RedisClient, stream_name: str) -> None:
        self._redis = redis
        self._stream_name = stream_name

    async def publish(self, event: EventCreate) -> str:
        envelope = StreamEnvelope(event=event, received_at=datetime.now(UTC))
        try:
            stream_id = await self._redis.xadd(
                self._stream_name,
                {"data": envelope.model_dump_json()},
            )
        except RedisError as exc:
            raise EventPublicationError("Redis Stream publication failed") from exc
        return stream_id.decode() if isinstance(stream_id, bytes) else stream_id

