from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.schemas.events import EventCreate, StreamEnvelope
from app.services.persistence import PersistenceOutcome
from app.workers.main import EventWorker, _create_worker_redis
from tests.helpers import FakeRedis, stream_fields


class FakePersistence:
    def __init__(
        self,
        outcome: PersistenceOutcome = PersistenceOutcome.INSERTED,
        *,
        fail: bool = False,
        operation_trace: list[str] | None = None,
        failure_parameter: str = "test database value",
    ) -> None:
        self.outcome = outcome
        self.fail = fail
        self.operation_trace = operation_trace
        self.failure_parameter = failure_parameter
        self.envelopes: list[StreamEnvelope] = []

    async def persist(self, envelope: StreamEnvelope) -> PersistenceOutcome:
        if self.operation_trace is not None:
            self.operation_trace.append("persistence_started")
        self.envelopes.append(envelope)
        if self.fail:
            if self.operation_trace is not None:
                self.operation_trace.append("persistence_failed")
            raise OperationalError(
                "INSERT",
                {"value": self.failure_parameter},
                OSError("test database unavailable"),
            )
        if self.operation_trace is not None:
            self.operation_trace.append(f"persistence_{self.outcome.value}")
        return self.outcome


class ConflictTraceHandler(logging.Handler):
    def __init__(self, operation_trace: list[str]) -> None:
        super().__init__(level=logging.ERROR)
        self._operation_trace = operation_trace

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "event_name", None) == "worker.message.idempotency_conflict":
            self._operation_trace.append("conflict_logged")


def make_envelope() -> StreamEnvelope:
    return StreamEnvelope(
        event=EventCreate(
            event_id=UUID("339a2050-db93-4357-81dd-3bc255d70776"),
            service="checkout",
            metric_name="error_count",
            value=1,
            timestamp=datetime(2026, 8, 5, tzinfo=UTC),
        ),
        received_at=datetime(2026, 8, 5, 0, 0, 1, tzinfo=UTC),
    )


async def test_worker_acknowledges_after_persister_returns_inserted(
    settings: Settings,
) -> None:
    operation_trace: list[str] = []
    redis = FakeRedis(operation_trace=operation_trace)
    persistence = FakePersistence(operation_trace=operation_trace)
    worker = EventWorker(redis, persistence, settings)
    envelope = make_envelope()

    await worker.process_message(b"1-0", stream_fields(envelope.model_dump_json()))

    assert persistence.envelopes == [envelope]
    assert redis.acknowledged == [(settings.redis_stream, settings.redis_consumer_group, (b"1-0",))]
    assert operation_trace == ["persistence_started", "persistence_inserted", "xack"]


async def test_worker_acknowledges_after_persister_confirms_exact_duplicate(
    settings: Settings,
) -> None:
    operation_trace: list[str] = []
    redis = FakeRedis(operation_trace=operation_trace)
    persistence = FakePersistence(
        PersistenceOutcome.DUPLICATE,
        operation_trace=operation_trace,
    )
    worker = EventWorker(redis, persistence, settings)

    await worker.process_message(b"2-0", stream_fields(make_envelope().model_dump_json()))

    assert len(redis.acknowledged) == 1
    assert operation_trace == ["persistence_started", "persistence_duplicate", "xack"]


async def test_worker_logs_and_acknowledges_idempotency_conflict_after_persistence(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    operation_trace: list[str] = []
    redis = FakeRedis(operation_trace=operation_trace)
    persistence = FakePersistence(
        PersistenceOutcome.IDEMPOTENCY_CONFLICT,
        operation_trace=operation_trace,
    )
    worker = EventWorker(redis, persistence, settings)
    caplog.set_level(logging.ERROR, logger="app.workers.main")
    sensitive_value = "distinctive-conflicting-payload-value"
    envelope = make_envelope()
    envelope.event.tags["secret"] = sensitive_value
    trace_handler = ConflictTraceHandler(operation_trace)
    worker_logger = logging.getLogger("app.workers.main")
    worker_logger.addHandler(trace_handler)

    try:
        await worker.process_message(b"2-1", stream_fields(envelope.model_dump_json()))
    finally:
        worker_logger.removeHandler(trace_handler)

    assert len(redis.acknowledged) == 1
    assert operation_trace == [
        "persistence_started",
        "persistence_idempotency_conflict",
        "conflict_logged",
        "xack",
    ]
    assert sensitive_value not in caplog.text
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "worker.message.idempotency_conflict"
    )
    assert getattr(record, "error_category", None) == "IdempotencyConflict"
    assert getattr(record, "processing_stage", None) == "idempotency_validation"
    assert getattr(record, "event_id", None) == str(envelope.event.event_id)
    assert record.exc_info is None


async def test_worker_with_fake_persister_does_not_ack_operational_error(
    settings: Settings,
) -> None:
    operation_trace: list[str] = []
    redis = FakeRedis(operation_trace=operation_trace)
    worker = EventWorker(
        redis,
        FakePersistence(fail=True, operation_trace=operation_trace),
        settings,
    )

    await worker.process_message(b"3-0", stream_fields(make_envelope().model_dump_json()))

    assert redis.acknowledged == []
    assert operation_trace == ["persistence_started", "persistence_failed"]


async def test_worker_with_fake_redis_logs_xack_error_without_success(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    operation_trace: list[str] = []
    redis = FakeRedis(fail_xack=True, operation_trace=operation_trace)
    worker = EventWorker(
        redis,
        FakePersistence(operation_trace=operation_trace),
        settings,
    )
    envelope = make_envelope()
    caplog.set_level(logging.INFO, logger="app.workers.main")

    await worker.process_message(b"3-1", stream_fields(envelope.model_dump_json()))

    event_names = {
        getattr(record, "event_name", None) for record in caplog.records
    }
    assert redis.acknowledged == []
    assert operation_trace == ["persistence_started", "persistence_inserted", "xack"]
    assert "worker.message.acknowledged" not in event_names
    assert "worker.message.idempotency_conflict_acknowledged" not in event_names
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "worker.message.ack_failed"
    )
    assert getattr(record, "stream_message_id", None) == "3-1"
    assert getattr(record, "event_id", None) == str(envelope.event.event_id)
    assert getattr(record, "persistence_outcome", None) == "inserted"
    assert getattr(record, "error_category", None) == "RedisError"
    assert getattr(record, "processing_stage", None) == "stream_acknowledgement"
    assert record.exc_info is None


@pytest.mark.parametrize("acknowledged_count", [0, 2])
async def test_worker_with_fake_redis_logs_non_unit_xack_count_without_success(
    acknowledged_count: int,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    redis = FakeRedis(xack_result=acknowledged_count)
    worker = EventWorker(redis, FakePersistence(), settings)
    envelope = make_envelope()
    caplog.set_level(logging.INFO, logger="app.workers.main")

    await worker.process_message(b"3-2", stream_fields(envelope.model_dump_json()))

    event_names = {
        getattr(record, "event_name", None) for record in caplog.records
    }
    assert redis.acknowledged == [
        (settings.redis_stream, settings.redis_consumer_group, (b"3-2",))
    ]
    assert "worker.message.acknowledged" not in event_names
    assert "worker.message.idempotency_conflict_acknowledged" not in event_names
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "worker.message.ack_missing"
    )
    assert getattr(record, "stream_message_id", None) == "3-2"
    assert getattr(record, "event_id", None) == str(envelope.event.event_id)
    assert getattr(record, "persistence_outcome", None) == "inserted"
    assert getattr(record, "acknowledged_count", None) == acknowledged_count
    assert getattr(record, "processing_stage", None) == "stream_acknowledgement"
    assert record.exc_info is None


async def test_worker_leaves_invalid_payload_pending(settings: Settings) -> None:
    redis = FakeRedis()
    persistence = FakePersistence()
    worker = EventWorker(redis, persistence, settings)

    await worker.process_message(b"4-0", {b"data": b"not-json"})

    assert persistence.envelopes == []
    assert redis.acknowledged == []


async def test_worker_sanitizes_invalid_payload_logs(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_value = "distinctive-sensitive-tag-value"
    raw_payload = (
        '{"event":{"event_id":"339a2050-db93-4357-81dd-3bc255d70776",'
        '"service":"checkout","metric_name":"latency_ms",'
        '"value":1e308,"timestamp":"2026-08-05T00:00:00Z",'
        f'"tags":{{"secret":"{sensitive_value}"}}}},'
        '"received_at":"2026-08-05T00:00:01Z"}'
    )
    worker = EventWorker(FakeRedis(), FakePersistence(), settings)
    caplog.set_level(logging.WARNING, logger="app.workers.main")

    await worker.process_message(b"5-0", stream_fields(raw_payload))

    assert sensitive_value not in caplog.text
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "worker.message.invalid"
    )
    assert getattr(record, "error_category", None) == "ValidationError"
    assert getattr(record, "validation_error_count", None) == 1
    assert record.exc_info is None


async def test_worker_sanitizes_database_failure_logs(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_value = "distinctive-database-parameter"
    worker = EventWorker(
        FakeRedis(),
        FakePersistence(fail=True, failure_parameter=sensitive_value),
        settings,
    )
    caplog.set_level(logging.ERROR, logger="app.workers.main")

    await worker.process_message(b"6-0", stream_fields(make_envelope().model_dump_json()))

    assert sensitive_value not in caplog.text
    record = next(
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "worker.message.persistence_failed"
    )
    assert getattr(record, "error_category", None) == "OperationalError"
    assert getattr(record, "metric_name", None) == "error_count"
    assert getattr(record, "processing_stage", None) == "database_persistence"
    assert record.exc_info is None


async def test_worker_creates_named_group(settings: Settings) -> None:
    redis = FakeRedis()
    worker = EventWorker(redis, FakePersistence(), settings)

    await worker.ensure_consumer_group()

    assert redis.groups == [
        (settings.redis_stream, settings.redis_consumer_group, "0-0", True)
    ]


async def test_worker_redis_timeout_exceeds_block_interval(settings: Settings) -> None:
    redis = _create_worker_redis(settings)

    try:
        socket_timeout = redis.connection_pool.connection_kwargs["socket_timeout"]
        assert socket_timeout == settings.redis_block_ms / 1_000 + 5.0
        assert socket_timeout > settings.redis_block_ms / 1_000
    finally:
        await redis.aclose()
