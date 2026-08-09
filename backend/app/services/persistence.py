from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.metric_event import MetricEvent
from app.schemas.events import StreamEnvelope


class PersistenceOutcome(StrEnum):
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


class EventPersistenceService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def persist(self, envelope: StreamEnvelope) -> PersistenceOutcome:
        event = envelope.event
        processed_at = datetime.now(UTC)
        async with self._session_factory() as session:
            try:
                async with session.begin():
                    session.add(
                        MetricEvent(
                            event_id=event.event_id,
                            service=event.service,
                            metric_name=event.metric_name.value,
                            value=event.value,
                            event_timestamp=event.timestamp,
                            tags=event.tags,
                            received_at=envelope.received_at,
                            processed_at=processed_at,
                            schema_version=event.schema_version,
                        )
                    )
                    await session.flush()
            except IntegrityError:
                await session.rollback()
                existing_event = await session.scalar(
                    select(MetricEvent).where(MetricEvent.event_id == event.event_id)
                )
                if existing_event is None:
                    raise
                if _matches_client_event(existing_event, envelope):
                    return PersistenceOutcome.DUPLICATE
                return PersistenceOutcome.IDEMPOTENCY_CONFLICT
        return PersistenceOutcome.INSERTED


def _matches_client_event(existing: MetricEvent, envelope: StreamEnvelope) -> bool:
    event = envelope.event
    return (
        existing.service == event.service
        and existing.metric_name == event.metric_name.value
        and existing.value == event.value
        and existing.event_timestamp == event.timestamp
        and existing.tags == event.tags
        and existing.schema_version == event.schema_version
    )
