from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_event_publisher, get_event_query_service
from app.api.parameters import MAX_EVENT_PAGE
from app.schemas.events import (
    MAX_ABSOLUTE_METRIC_VALUE,
    EventAccepted,
    EventCreate,
    EventPage,
    EventRead,
    MetricSummary,
)
from app.services.publisher import EventPublicationError, EventPublisher
from app.services.queries import EventFilters, EventQueryService


def valid_payload() -> dict[str, object]:
    return {
        "service": "  Checkout  ",
        "metric_name": "latency_ms",
        "value": 12.5,
        "timestamp": "2026-08-05T12:00:00-05:00",
        "tags": {"region": "us-central"},
        "schema_version": 1,
    }


class RecordingPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[EventCreate] = []

    async def publish(self, event: EventCreate) -> str:
        self.events.append(event)
        if self.fail:
            raise EventPublicationError("unavailable")
        return "1700000000000-0"


class StubQueryService(EventQueryService):
    def __init__(self) -> None:
        self.filters: EventFilters | None = None
        self.requested_page: tuple[int, int] | None = None

    async def list_events(
        self,
        filters: EventFilters,
        *,
        page: int,
        page_size: int,
    ) -> EventPage:
        self.filters = filters
        self.requested_page = (page, page_size)
        return EventPage(
            items=[
                EventRead(
                    id=7,
                    event_id=uuid4(),
                    service="checkout",
                    metric_name="latency_ms",
                    value=12.5,
                    event_timestamp=datetime(2026, 8, 5, 17, tzinfo=UTC),
                    tags={},
                    schema_version=1,
                    received_at=datetime(2026, 8, 5, 17, tzinfo=UTC),
                    processed_at=datetime(2026, 8, 5, 17, tzinfo=UTC),
                )
            ],
            page=page,
            page_size=page_size,
            total=1,
        )

    async def summarize(self, filters: EventFilters) -> MetricSummary:
        self.filters = filters
        return MetricSummary(
            event_count=2,
            min_value=10,
            max_value=20,
            average_value=15,
            sum_value=30,
            most_recent_value=20,
            most_recent_timestamp=datetime(2026, 8, 5, 17, tzinfo=UTC),
        )


def override_publisher(app: FastAPI, publisher: RecordingPublisher) -> None:
    app.dependency_overrides[get_event_publisher] = lambda: cast(EventPublisher, publisher)


def test_valid_event_is_accepted_only_after_publication(app: FastAPI) -> None:
    publisher = RecordingPublisher()
    override_publisher(app, publisher)

    response = TestClient(app).post("/api/v1/events", json=valid_payload())

    assert response.status_code == 202
    response_body = EventAccepted.model_validate(response.json())
    assert isinstance(response_body.event_id, UUID)
    assert response_body.status == "accepted"
    assert response_body.stream_id == "1700000000000-0"
    assert publisher.events[0].event_id == response_body.event_id
    assert publisher.events[0].service == "checkout"


def test_publication_failure_returns_service_unavailable(app: FastAPI) -> None:
    override_publisher(app, RecordingPublisher(fail=True))

    response = TestClient(app).post("/api/v1/events", json=valid_payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Event stream is unavailable"}


def test_invalid_ingestion_payloads_return_422_without_publication(app: FastAPI) -> None:
    publisher = RecordingPublisher()
    override_publisher(app, publisher)
    invalid_payloads: list[dict[str, object]] = []
    for field, value in (
        ("service", "  "),
        ("metric_name", "unsupported"),
        ("timestamp", "not-a-time"),
        ("timestamp", "2026-08-05T12:00:00"),
        ("schema_version", 9),
        ("tags", {f"key-{index}": "value" for index in range(21)}),
        ("tags", {"x" * 65: "value"}),
        ("tags", {"key": "x" * 257}),
    ):
        payload = valid_payload()
        payload[field] = value
        invalid_payloads.append(payload)

    with TestClient(app) as client:
        for payload in invalid_payloads:
            assert client.post("/api/v1/events", json=payload).status_code == 422
    assert publisher.events == []


@pytest.mark.parametrize("value_literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_numbers_return_422_without_publication(
    app: FastAPI,
    value_literal: str,
) -> None:
    publisher = RecordingPublisher()
    override_publisher(app, publisher)
    payload = (
        '{"service":"checkout","metric_name":"latency_ms","value":'
        f'{value_literal},"timestamp":"2026-08-05T12:00:00Z"}}'
    )

    response = TestClient(app).post(
        "/api/v1/events",
        content=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert publisher.events == []


def test_event_listing_contract_pagination_and_filters(app: FastAPI) -> None:
    query_service = StubQueryService()
    app.dependency_overrides[get_event_query_service] = lambda: query_service

    response = TestClient(app).get(
        "/api/v1/events",
        params={
            "page": 2,
            "page_size": 10,
            "service": " Checkout ",
            "metric_name": "latency_ms",
            "start": "2026-08-05T10:00:00-05:00",
            "end": "2026-08-05T12:00:00-05:00",
        },
    )

    assert response.status_code == 200
    assert set(response.json()) == {"items", "page", "page_size", "total"}
    assert response.json()["items"][0]["id"] == 7
    assert query_service.requested_page == (2, 10)
    assert query_service.filters is not None
    assert query_service.filters.service == "checkout"
    assert query_service.filters.start == datetime(2026, 8, 5, 15, tzinfo=UTC)


def test_summary_contract_and_filters(app: FastAPI) -> None:
    query_service = StubQueryService()
    app.dependency_overrides[get_event_query_service] = lambda: query_service

    response = TestClient(app).get(
        "/api/v1/metrics/summary",
        params={"service": "checkout", "metric_name": "latency_ms"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "event_count": 2,
        "min_value": 10.0,
        "max_value": 20.0,
        "average_value": 15.0,
        "sum_value": 30.0,
        "most_recent_value": 20.0,
        "most_recent_timestamp": "2026-08-05T17:00:00Z",
    }


def test_summary_requires_metric_name(app: FastAPI) -> None:
    query_service = StubQueryService()
    app.dependency_overrides[get_event_query_service] = lambda: query_service

    response = TestClient(app).get("/api/v1/metrics/summary")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "metric_name"]
    assert query_service.filters is None


def test_pagination_limit_prevents_database_offset_overflow(app: FastAPI) -> None:
    query_service = StubQueryService()
    app.dependency_overrides[get_event_query_service] = lambda: query_service
    client = TestClient(app)

    maximum = client.get("/api/v1/events", params={"page": MAX_EVENT_PAGE})
    above_maximum = client.get("/api/v1/events", params={"page": MAX_EVENT_PAGE + 1})
    huge = client.get(
        "/api/v1/events",
        params={"page": 9_223_372_036_854_775_808, "page_size": 100},
    )

    assert maximum.status_code == 200
    assert maximum.json()["page"] == MAX_EVENT_PAGE
    assert above_maximum.status_code == 422
    assert huge.status_code == 422


def test_metric_value_limit_is_enforced_by_ingestion_api(app: FastAPI) -> None:
    publisher = RecordingPublisher()
    override_publisher(app, publisher)
    client = TestClient(app)
    at_limit_payload = valid_payload()
    at_limit_payload["value"] = MAX_ABSOLUTE_METRIC_VALUE
    above_limit_payload = valid_payload()
    above_limit_payload["value"] = MAX_ABSOLUTE_METRIC_VALUE + 1

    assert client.post("/api/v1/events", json=at_limit_payload).status_code == 202
    assert client.post("/api/v1/events", json=above_limit_payload).status_code == 422
    assert len(publisher.events) == 1


def test_query_timestamps_must_be_aware_and_ordered(app: FastAPI) -> None:
    query_service = StubQueryService()
    app.dependency_overrides[get_event_query_service] = lambda: query_service
    client = TestClient(app)

    naive = client.get("/api/v1/events", params={"start": "2026-08-05T10:00:00"})
    reversed_range = client.get(
        "/api/v1/events",
        params={
            "start": "2026-08-05T12:00:00Z",
            "end": "2026-08-05T10:00:00Z",
        },
    )

    assert naive.status_code == 422
    assert reversed_range.status_code == 422
