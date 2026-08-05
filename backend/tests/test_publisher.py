from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.schemas.events import EventCreate, StreamEnvelope
from app.services.publisher import EventPublicationError, EventPublisher
from tests.helpers import FakeRedis


def make_event() -> EventCreate:
    return EventCreate(
        service="api",
        metric_name="request_count",
        value=1,
        timestamp=datetime(2026, 8, 5, tzinfo=UTC),
    )


async def test_publisher_xadds_one_canonical_envelope() -> None:
    redis = FakeRedis()
    publisher = EventPublisher(redis, "eventstream:test")
    event = make_event()

    stream_id = await publisher.publish(event)

    assert stream_id == "1700000000000-0"
    assert len(redis.added) == 1
    stream_name, fields = redis.added[0]
    assert stream_name == "eventstream:test"
    envelope = StreamEnvelope.model_validate_json(fields["data"])
    assert envelope.event == event
    assert envelope.received_at.tzinfo is not None


async def test_publisher_surfaces_redis_failure() -> None:
    publisher = EventPublisher(FakeRedis(fail_xadd=True), "eventstream:test")

    with pytest.raises(EventPublicationError):
        await publisher.publish(make_event())

