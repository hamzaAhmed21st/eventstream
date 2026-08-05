from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.events import MAX_ABSOLUTE_METRIC_VALUE, EventCreate, MetricName


def valid_event_data() -> dict[str, object]:
    return {
        "service": "  Checkout-API  ",
        "metric_name": "latency_ms",
        "value": 42.5,
        "timestamp": "2026-08-05T12:00:00-05:00",
        "tags": {"region": "us-central"},
        "schema_version": 1,
    }


def test_valid_event_is_normalized_and_default_id_is_stable() -> None:
    event = EventCreate.model_validate(valid_event_data())

    assert isinstance(event.event_id, UUID)
    assert event.event_id == event.event_id
    assert event.service == "checkout-api"
    assert event.metric_name is MetricName.LATENCY_MS
    assert event.timestamp == datetime(2026, 8, 5, 17, tzinfo=UTC)


def test_default_event_ids_are_unique_per_event() -> None:
    first = EventCreate.model_validate(valid_event_data())
    second = EventCreate.model_validate(valid_event_data())

    assert first.event_id != second.event_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("service", "   "),
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


def test_non_utc_timezone_is_converted_to_utc() -> None:
    data = valid_event_data()
    data["timestamp"] = datetime(2026, 8, 5, 12, tzinfo=timezone(timedelta(hours=3)))

    event = EventCreate.model_validate(data)

    assert event.timestamp == datetime(2026, 8, 5, 9, tzinfo=UTC)


@pytest.mark.parametrize(
    "value",
    [-MAX_ABSOLUTE_METRIC_VALUE, MAX_ABSOLUTE_METRIC_VALUE],
)
def test_metric_value_limit_is_accepted(value: float) -> None:
    data = valid_event_data()
    data["value"] = value

    assert EventCreate.model_validate(data).value == value


@pytest.mark.parametrize(
    "value",
    [-(MAX_ABSOLUTE_METRIC_VALUE + 1), MAX_ABSOLUTE_METRIC_VALUE + 1, 1e308],
)
def test_metric_values_above_safe_limit_are_rejected(value: float) -> None:
    data = valid_event_data()
    data["value"] = value

    with pytest.raises(ValidationError):
        EventCreate.model_validate(data)
