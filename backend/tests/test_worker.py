from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.schemas.events import EventCreate, StreamEnvelope
from app.services.persistence import PersistenceOutcome
from app.workers.main import EventWorker
from tests.helpers import FakeRedis, stream_fields


class FakePersistence:
    def __init__(
        self,
        outcome: PersistenceOutcome = PersistenceOutcome.INSERTED,
        *,
        fail: bool = False,
    ) -> None:
        self.outcome = outcome
        self.fail = fail
        self.envelopes: list[StreamEnvelope] = []

    async def persist(self, envelope: StreamEnvelope) -> PersistenceOutcome:
        self.envelopes.append(envelope)
        if self.fail:
            raise OperationalError("INSERT", {}, OSError("test database unavailable"))
        return self.outcome


def make_envelope() -> StreamEnvelope:
    return StreamEnvelope(
        event=EventCreate(
            service="checkout",
            metric_name="error_count",
            value=1,
            timestamp=datetime(2026, 8, 5, tzinfo=UTC),
        ),
        received_at=datetime(2026, 8, 5, 0, 0, 1, tzinfo=UTC),
    )


async def test_worker_acknowledges_only_after_insert(settings: Settings) -> None:
    redis = FakeRedis()
    persistence = FakePersistence()
    worker = EventWorker(redis, persistence, settings)
    envelope = make_envelope()

    await worker.process_message(b"1-0", stream_fields(envelope.model_dump_json()))

    assert persistence.envelopes == [envelope]
    assert redis.acknowledged == [(settings.redis_stream, settings.redis_consumer_group, (b"1-0",))]


async def test_worker_acknowledges_confirmed_duplicate(settings: Settings) -> None:
    redis = FakeRedis()
    persistence = FakePersistence(PersistenceOutcome.DUPLICATE)
    worker = EventWorker(redis, persistence, settings)

    await worker.process_message(b"2-0", stream_fields(make_envelope().model_dump_json()))

    assert len(redis.acknowledged) == 1


async def test_worker_leaves_database_failure_pending(settings: Settings) -> None:
    redis = FakeRedis()
    worker = EventWorker(redis, FakePersistence(fail=True), settings)

    await worker.process_message(b"3-0", stream_fields(make_envelope().model_dump_json()))

    assert redis.acknowledged == []


async def test_worker_leaves_invalid_payload_pending(settings: Settings) -> None:
    redis = FakeRedis()
    persistence = FakePersistence()
    worker = EventWorker(redis, persistence, settings)

    await worker.process_message(b"4-0", {b"data": b"not-json"})

    assert persistence.envelopes == []
    assert redis.acknowledged == []


async def test_worker_creates_named_group(settings: Settings) -> None:
    redis = FakeRedis()
    worker = EventWorker(redis, FakePersistence(), settings)

    await worker.ensure_consumer_group()

    assert redis.groups == [
        (settings.redis_stream, settings.redis_consumer_group, "0-0", True)
    ]

