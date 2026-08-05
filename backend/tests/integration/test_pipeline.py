from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import Connection, delete, func, inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.protocols import RedisClient
from app.db.session import create_database_engine, create_session_factory
from app.models.metric_event import MetricEvent
from app.schemas.events import MAX_ABSOLUTE_METRIC_VALUE, EventCreate, MetricName, StreamEnvelope
from app.services.persistence import EventPersistenceService, PersistenceOutcome
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
    stop_event = asyncio.Event()
    worker_task: asyncio.Task[None] | None = None
    try:
        await _assert_migrated_schema(engine)
        redis_client = cast(RedisClient, redis)
        publisher = EventPublisher(redis_client, settings.redis_stream)
        worker = EventWorker(
            redis_client,
            EventPersistenceService(session_factory),
            settings,
        )
        worker_task = asyncio.create_task(worker.run(stop_event))
        await _wait_for_consumer_group(redis, settings)

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

        await _wait_for_processed_stream(
            redis,
            settings,
            session_factory,
            event_ids,
            expected_stream_entries=4,
            expected_stored_rows=3,
        )

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
        stop_event.set()
        if worker_task is not None:
            await asyncio.wait_for(worker_task, timeout=2)
        await _remove_test_rows(session_factory, event_ids)
        await redis.delete(settings.redis_stream)
        await redis.aclose()
        await engine.dispose()


class FailingPersistence:
    def __init__(self) -> None:
        self.called = asyncio.Event()

    async def persist(self, envelope: StreamEnvelope) -> PersistenceOutcome:
        self.called.set()
        raise OperationalError(
            "INSERT",
            {"event_id": str(envelope.event.event_id)},
            OSError("isolated integration failure"),
        )


@pytest.mark.asyncio
async def test_worker_loop_leaves_failed_persistence_pending(test_redis_url: str) -> None:
    redis = Redis.from_url(test_redis_url, decode_responses=False)
    unique_suffix = uuid4().hex
    settings = Settings(
        _env_file=None,
        redis_url=test_redis_url,
        redis_stream=f"eventstream:test:failed:{unique_suffix}",
        redis_consumer_group=f"eventstream-test-failed-workers-{unique_suffix}",
        redis_consumer_name="integration-failing-worker",
        redis_block_ms=100,
    )
    failing_persistence = FailingPersistence()
    redis_client = cast(RedisClient, redis)
    worker = EventWorker(redis_client, failing_persistence, settings)
    publisher = EventPublisher(redis_client, settings.redis_stream)
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(worker.run(stop_event))
    try:
        await _wait_for_consumer_group(redis, settings)
        await publisher.publish(
            EventCreate(
                service="checkout",
                metric_name=MetricName.ERROR_COUNT,
                value=1.0,
                timestamp=datetime(2026, 8, 5, 12, tzinfo=UTC),
            )
        )
        await asyncio.wait_for(failing_persistence.called.wait(), timeout=5)
        pending = await redis.xpending(settings.redis_stream, settings.redis_consumer_group)
        assert pending["pending"] == 1
    finally:
        stop_event.set()
        await asyncio.wait_for(worker_task, timeout=2)
        await redis.delete(settings.redis_stream)
        await redis.aclose()


@pytest.mark.asyncio
async def test_summary_aggregates_maximum_accepted_values(test_database_url: str) -> None:
    engine = create_database_engine(test_database_url)
    session_factory = create_session_factory(engine)
    persistence = EventPersistenceService(session_factory)
    event_ids: list[UUID] = []
    try:
        for minute in range(2):
            event = EventCreate(
                service="aggregation-boundary",
                metric_name=MetricName.LATENCY_MS,
                value=MAX_ABSOLUTE_METRIC_VALUE,
                timestamp=datetime(2026, 8, 5, 12, minute, tzinfo=UTC),
            )
            event_ids.append(event.event_id)
            await persistence.persist(
                StreamEnvelope(event=event, received_at=event.timestamp)
            )

        async with session_factory() as session:
            summary = await EventQueryService(session).summarize(
                EventFilters(
                    service="aggregation-boundary",
                    metric_name=MetricName.LATENCY_MS,
                )
            )
        assert summary.event_count == 2
        assert summary.average_value == MAX_ABSOLUTE_METRIC_VALUE
        assert summary.sum_value == 2 * MAX_ABSOLUTE_METRIC_VALUE
    finally:
        await _remove_test_rows(session_factory, event_ids)
        await engine.dispose()


async def _wait_for_consumer_group(redis: Redis, settings: Settings) -> None:
    async with asyncio.timeout(5):
        while True:
            try:
                groups = await redis.xinfo_groups(settings.redis_stream)
            except ResponseError:
                groups = []
            if groups:
                return
            await asyncio.sleep(0.05)


async def _wait_for_processed_stream(
    redis: Redis,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_ids: list[UUID],
    *,
    expected_stream_entries: int,
    expected_stored_rows: int,
) -> None:
    async with asyncio.timeout(5):
        while True:
            async with session_factory() as session:
                stored_count = await session.scalar(
                    select(func.count(MetricEvent.id)).where(
                        MetricEvent.event_id.in_(event_ids)
                    )
                )
            group_state = (await redis.xinfo_groups(settings.redis_stream))[0]
            if (
                await redis.xlen(settings.redis_stream) == expected_stream_entries
                and stored_count == expected_stored_rows
                and group_state["pending"] == 0
                and group_state["lag"] == 0
            ):
                return
            await asyncio.sleep(0.05)


async def _remove_test_rows(
    session_factory: async_sessionmaker[AsyncSession],
    event_ids: list[UUID],
) -> None:
    if not event_ids:
        return
    async with session_factory() as session, session.begin():
        await session.execute(delete(MetricEvent).where(MetricEvent.event_id.in_(event_ids)))
