from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.schemas.events import MetricName
from app.services.queries import EventFilters


def build_event_filters(
    service: str | None,
    metric_name: MetricName | None,
    start: datetime | None,
    end: datetime | None,
) -> EventFilters:
    normalized_service: str | None = None
    if service is not None:
        normalized_service = service.strip().lower()
        if not normalized_service:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="service filter cannot be empty",
            )

    normalized_start = _normalize_optional_timestamp(start, "start")
    normalized_end = _normalize_optional_timestamp(end, "end")
    if (
        normalized_start is not None
        and normalized_end is not None
        and normalized_start > normalized_end
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start must be less than or equal to end",
        )

    return EventFilters(
        service=normalized_service,
        metric_name=metric_name,
        start=normalized_start,
        end=normalized_end,
    )


def _normalize_optional_timestamp(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must include a timezone",
        )
    return value.astimezone(UTC)
