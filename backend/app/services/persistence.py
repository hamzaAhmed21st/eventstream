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
                existing_id = await session.scalar(
                    select(MetricEvent.id).where(MetricEvent.event_id == event.event_id)
                )
                if existing_id is None:
                    raise
                return PersistenceOutcome.DUPLICATE
        return PersistenceOutcome.INSERTED

