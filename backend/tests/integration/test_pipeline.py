from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import Connection, delete, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.protocols import RedisClient, RedisStreamBatch
from app.db.session import create_database_engine, create_session_factory
from app.models.metric_event import MetricEvent
from app.schemas.events import EventCreate, MetricName
from app.services.persistence import EventPersistenceService
from app.services.publisher import EventPublisher
from app.services.queries import EventFilters, EventQueryService
from app.workers.main import EventWorker

pytestmark = pytest.mark.integration

EXPECTED_COLUMNS = {
    "id",
    "event_id",
    "service",
    "metric_name",
    "value",
    "event_timestamp",
    "tags",
    "received_at",
    "processed_at",
    "schema_version",
}
EXPECTED_INDEXES = {
    "ix_metric_events_service",
    "ix_metric_events_metric_name",
    "ix_metric_events_event_timestamp",
    "ix_metric_events_service_metric_timestamp",
}


def _inspect_metric_events(connection: Connection) -> tuple[set[str], set[str], set[str]]:
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("metric_events")}
    indexes = {
        name
        for index in inspector.get_indexes("metric_events")
        if isinstance((name := index["name"]), str)
    }
    constraints = {
        name
        for constraint in inspector.get_unique_constraints("metric_events")
        if isinstance((name := constraint["name"]), str)
    }
    return columns, indexes, constraints


def _get_table_names(connection: Connection) -> list[str]:
    return inspect(connection).get_table_names()


async def _assert_migrated_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        table_names = await connection.run_sync(_get_table_names)
        if "metric_events" not in table_names:
            pytest.fail("metric_events is absent; run Alembic against TEST_DATABASE_URL first")
        columns, indexes, constraints = await connection.run_sync(_inspect_metric_events)

    assert columns == EXPECTED_COLUMNS
    assert indexes >= EXPECTED_INDEXES
    assert "uq_metric_events_event_id" in constraints


@pytest.mark.asyncio
async def test_authored_migration_matches_model_contract(test_database_url: str) -> None:
    engine = create_database_engine(test_database_url)
    try:
        await _assert_migrated_schema(engine)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_stream_worker_idempotency_queries_and_summary(
    test_database_url: str,
    test_redis_url: str,
) -> None:
    engine = create_database_engine(test_database_url)
    session_factory = create_session_factory(engine)
    redis = Redis.from_url(test_redis_url, decode_responses=False)
    unique_suffix = uuid4().hex
    settings = Settings(
        _env_file=None,
        database_url=test_database_url,
        redis_url=test_redis_url,
        redis_stream=f"eventstream:test:{unique_suffix}",
        redis_consumer_group=f"eventstream-test-workers-{unique_suffix}",
        redis_consumer_name="integration-worker",
        redis_block_ms=100,
    )
    event_ids: list[UUID] = []
    try:
        await _assert_migrated_schema(engine)
        redis_client = cast(RedisClient, redis)
        publisher = EventPublisher(redis_client, settings.redis_stream)
        worker = EventWorker(
            redis_client,
            EventPersistenceService(session_factory),
            settings,
        )
        await worker.ensure_consumer_group()

        base_timestamp = datetime(2026, 8, 5, 12, tzinfo=UTC)
        events = [
            EventCreate(
                service="checkout",
                metric_name=MetricName.LATENCY_MS,
                value=float(value),
                timestamp=base_timestamp + timedelta(minutes=index),
                tags={"source": "integration"},
            )
            for index, value in enumerate((10, 20, 30))
        ]
        event_ids.extend(event.event_id for event in events)
        for event in (*events, events[0]):
            await publisher.publish(event)

        assert await redis.xlen(settings.redis_stream) == 4
        batches = cast(
            list[RedisStreamBatch],
            await redis.xreadgroup(
                settings.redis_consumer_group,
                settings.redis_consumer_name,
                {settings.redis_stream: ">"},
                count=10,
                block=1_000,
            ),
        )
        assert len(batches) == 1
        assert len(batches[0][1]) == 4
        for message_id, fields in batches[0][1]:
            await worker.process_message(message_id, fields)

        pending = await redis.xpending(settings.redis_stream, settings.redis_consumer_group)
        assert pending["pending"] == 0

        async with session_factory() as session:
            stored_count = await session.scalar(
                select(func.count(MetricEvent.id)).where(MetricEvent.event_id.in_(event_ids))
            )
            assert stored_count == 3

            query_service = EventQueryService(session)
            filters = EventFilters(
                service="checkout",
                metric_name=MetricName.LATENCY_MS,
                start=base_timestamp,
                end=base_timestamp + timedelta(minutes=2),
            )
            first_page = await query_service.list_events(filters, page=1, page_size=2)
            second_page = await query_service.list_events(filters, page=2, page_size=2)
            assert first_page.total == 3
            assert [item.value for item in first_page.items] == [30.0, 20.0]
            assert [item.value for item in second_page.items] == [10.0]

            summary = await query_service.summarize(filters)
            assert summary.event_count == 3
            assert summary.min_value == 10.0
            assert summary.max_value == 30.0
            assert summary.average_value == 20.0
            assert summary.sum_value == 60.0
            assert summary.most_recent_value == 30.0
            assert summary.most_recent_timestamp == base_timestamp + timedelta(minutes=2)

            empty_summary = await query_service.summarize(
                EventFilters(service="service-with-no-events")
            )
            assert empty_summary.model_dump() == {
                "event_count": 0,
                "min_value": None,
                "max_value": None,
                "average_value": None,
                "sum_value": None,
                "most_recent_value": None,
                "most_recent_timestamp": None,
            }
    finally:
        await _remove_test_rows(session_factory, event_ids)
        await redis.delete(settings.redis_stream)
        await redis.aclose()
        await engine.dispose()


async def _remove_test_rows(
    session_factory: async_sessionmaker[AsyncSession],
    event_ids: list[UUID],
) -> None:
    if not event_ids:
        return
    async with session_factory() as session, session.begin():
        await session.execute(delete(MetricEvent).where(MetricEvent.event_id.in_(event_ids)))
