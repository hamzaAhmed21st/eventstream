from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric_event import MetricEvent
from app.schemas.events import EventPage, EventRead, MetricName, MetricSummary


@dataclass(frozen=True, slots=True)
class EventFilters:
    service: str | None = None
    metric_name: MetricName | None = None
    start: datetime | None = None
    end: datetime | None = None


class EventQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_events(
        self,
        filters: EventFilters,
        *,
        page: int,
        page_size: int,
    ) -> EventPage:
        count_statement = _apply_filters(
            select(func.count(MetricEvent.id)),
            filters,
        )
        total = int((await self._session.scalar(count_statement)) or 0)

        events_statement = _apply_filters(select(MetricEvent), filters).order_by(
            MetricEvent.event_timestamp.desc(),
            MetricEvent.id.desc(),
        )
        events_statement = events_statement.offset((page - 1) * page_size).limit(page_size)
        result = await self._session.scalars(events_statement)
        items = [EventRead.model_validate(event) for event in result.all()]
        return EventPage(items=items, page=page, page_size=page_size, total=total)

    async def summarize(self, filters: EventFilters) -> MetricSummary:
        aggregates_statement = _apply_filters(
            select(
                func.count(MetricEvent.id),
                func.min(MetricEvent.value),
                func.max(MetricEvent.value),
                func.avg(MetricEvent.value),
                func.sum(MetricEvent.value),
            ),
            filters,
        )
        aggregate_row = (await self._session.execute(aggregates_statement)).one()
        event_count = int(aggregate_row[0])
        if event_count == 0:
            return MetricSummary(
                event_count=0,
                min_value=None,
                max_value=None,
                average_value=None,
                sum_value=None,
                most_recent_value=None,
                most_recent_timestamp=None,
            )

        recent_statement = _apply_filters(
            select(MetricEvent.value, MetricEvent.event_timestamp),
            filters,
        ).order_by(MetricEvent.event_timestamp.desc(), MetricEvent.id.desc()).limit(1)
        recent_row = (await self._session.execute(recent_statement)).one()
        return MetricSummary(
            event_count=event_count,
            min_value=float(aggregate_row[1]),
            max_value=float(aggregate_row[2]),
            average_value=float(aggregate_row[3]),
            sum_value=float(aggregate_row[4]),
            most_recent_value=float(recent_row[0]),
            most_recent_timestamp=recent_row[1],
        )


def _apply_filters[SelectRow: tuple[object, ...]](
    statement: Select[SelectRow],
    filters: EventFilters,
) -> Select[SelectRow]:
    if filters.service is not None:
        statement = statement.where(MetricEvent.service == filters.service)
    if filters.metric_name is not None:
        statement = statement.where(MetricEvent.metric_name == filters.metric_name.value)
    if filters.start is not None:
        statement = statement.where(MetricEvent.event_timestamp >= filters.start)
    if filters.end is not None:
        statement = statement.where(MetricEvent.event_timestamp <= filters.end)
    return statement
