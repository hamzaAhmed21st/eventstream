from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.events import EventCreate, MetricName

TEST_EVENT_ID = UUID("dc20c5cd-4f19-4f43-a0bf-4069ccab8a82")


def valid_event_data() -> dict[str, object]:
    return {
        "event_id": str(TEST_EVENT_ID),
        "service": "  Checkout-API  ",
        "metric_name": "latency_ms",
        "value": 42.5,
        "timestamp": "2026-08-05T12:00:00-05:00",
        "tags": {"region": "us-central"},
        "schema_version": 1,
    }


def test_valid_event_is_normalized_and_preserves_client_id() -> None:
    event = EventCreate.model_validate(valid_event_data())

    assert event.event_id == TEST_EVENT_ID
    assert event.service == "checkout-api"
    assert event.metric_name is MetricName.LATENCY_MS
    assert event.timestamp == datetime(2026, 8, 5, 17, tzinfo=UTC)


def test_event_id_is_required() -> None:
    data = valid_event_data()
    del data["event_id"]

    with pytest.raises(ValidationError):
        EventCreate.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("service", "   "),
        ("service", "checkout\x00api"),
        ("service", "x" * 129),
        ("metric_name", "disk_usage"),
        ("value", float("nan")),
        ("value", float("inf")),
        ("value", float("-inf")),
        ("value", True),
        ("value", "42.5"),
        ("timestamp", "2026-08-05T12:00:00"),
        ("timestamp", "not-a-timestamp"),
        ("schema_version", 2),
        ("schema_version", "1"),
        ("schema_version", 1.0),
        ("schema_version", True),
    ],
)
def test_invalid_event_fields_are_rejected(field: str, value: object) -> None:
    data = valid_event_data()
    data[field] = value

    with pytest.raises(ValidationError):
        EventCreate.model_validate(data)


@pytest.mark.parametrize(
    "tags",
    [
        {f"key-{index}": "value" for index in range(21)},
        {"k" * 65: "value"},
        {"key": "v" * 257},
        {"": "value"},
        {"nul\x00key": "value"},
        {"key": "nul\x00value"},
    ],
)
def test_tag_bounds_are_enforced(tags: dict[str, str]) -> None:
    data = valid_event_data()
    data["tags"] = tags

    with pytest.raises(ValidationError):
        EventCreate.model_validate(data)


def test_null_tags_are_normalized_to_empty_map() -> None:
    data = valid_event_data()
    data["tags"] = None

    event = EventCreate.model_validate(data)

    assert event.tags == {}


def test_service_length_is_checked_after_normalization() -> None:
    data = valid_event_data()
    data["service"] = f"  {'A' * 128}  "

    event = EventCreate.model_validate(data)

    assert event.service == "a" * 128


def test_non_utc_timezone_is_converted_to_utc() -> None:
    data = valid_event_data()
    data["timestamp"] = datetime(2026, 8, 5, 12, tzinfo=timezone(timedelta(hours=3)))

    event = EventCreate.model_validate(data)

    assert event.timestamp == datetime(2026, 8, 5, 9, tzinfo=UTC)


@pytest.mark.parametrize(
    ("metric_name", "value"),
    [
        (MetricName.LATENCY_MS, 0.0),
        (MetricName.LATENCY_MS, 86_400_000.0),
        (MetricName.REQUEST_COUNT, 0.0),
        (MetricName.REQUEST_COUNT, 1_000_000_000.0),
        (MetricName.ERROR_COUNT, 1_000_000_000.0),
        (MetricName.CPU_USAGE, 0.0),
        (MetricName.CPU_USAGE, 100.0),
        (MetricName.MEMORY_USAGE, 100.0),
    ],
)
def test_metric_contract_boundaries_are_accepted(
    metric_name: MetricName,
    value: float,
) -> None:
    data = valid_event_data()
    data["metric_name"] = metric_name
    data["value"] = value

    assert EventCreate.model_validate(data).value == value


@pytest.mark.parametrize(
    ("metric_name", "value"),
    [
        (MetricName.LATENCY_MS, -0.1),
        (MetricName.LATENCY_MS, 86_400_000.1),
        (MetricName.REQUEST_COUNT, -1.0),
        (MetricName.REQUEST_COUNT, 1.5),
        (MetricName.REQUEST_COUNT, 1_000_000_001.0),
        (MetricName.ERROR_COUNT, 0.5),
        (MetricName.CPU_USAGE, -0.1),
        (MetricName.CPU_USAGE, 100.1),
        (MetricName.MEMORY_USAGE, 100.1),
    ],
)
def test_values_outside_metric_contract_are_rejected(
    metric_name: MetricName,
    value: float,
) -> None:
    data = valid_event_data()
    data["metric_name"] = metric_name
    data["value"] = value

    with pytest.raises(ValidationError):
        EventCreate.model_validate(data)
