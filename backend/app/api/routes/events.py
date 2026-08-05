from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_event_publisher, get_event_query_service
from app.api.parameters import build_event_filters
from app.schemas.events import (
    EventAccepted,
    EventCreate,
    EventPage,
    MetricName,
    MetricSummary,
)
from app.services.publisher import EventPublicationError, EventPublisher
from app.services.queries import EventQueryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["events"])


@router.post("/events", response_model=EventAccepted, status_code=status.HTTP_202_ACCEPTED)
async def accept_event(
    event: EventCreate,
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> EventAccepted:
    try:
        stream_id = await publisher.publish(event)
    except EventPublicationError as exc:
        logger.warning(
            "Redis rejected an otherwise valid metric event",
            extra={"event_name": "api.event.publish_failed", "event_id": str(event.event_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event stream is unavailable",
        ) from exc

    logger.info(
        "Metric event accepted into the Redis Stream",
        extra={
            "event_name": "api.event.accepted",
            "event_id": str(event.event_id),
            "stream_id": stream_id,
        },
    )
    return EventAccepted(event_id=event.event_id, stream_id=stream_id)


@router.get("/events", response_model=EventPage)
async def list_events(
    query_service: Annotated[EventQueryService, Depends(get_event_query_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    service: Annotated[str | None, Query(max_length=128)] = None,
    metric_name: MetricName | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> EventPage:
    filters = build_event_filters(service, metric_name, start, end)
    return await query_service.list_events(filters, page=page, page_size=page_size)


@router.get("/metrics/summary", response_model=MetricSummary)
async def summarize_metrics(
    query_service: Annotated[EventQueryService, Depends(get_event_query_service)],
    service: Annotated[str | None, Query(max_length=128)] = None,
    metric_name: MetricName | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> MetricSummary:
    filters = build_event_filters(service, metric_name, start, end)
    return await query_service.summarize(filters)
