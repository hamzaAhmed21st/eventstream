from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.metrics import METRIC_SPECIFICATIONS
from app.db.base import Base


def _sql_number(value: float) -> str:
    return format(value, ".15g")


def _supported_metric_names_sql() -> str:
    return ", ".join(f"'{metric_name.value}'" for metric_name in METRIC_SPECIFICATIONS)


def _metric_value_semantics_sql() -> str:
    clauses: list[str] = []
    for metric_name, specification in METRIC_SPECIFICATIONS.items():
        requirements = [
            f"value >= {_sql_number(specification.minimum)}",
            f"value <= {_sql_number(specification.maximum)}",
        ]
        if specification.integral:
            requirements.append("value = trunc(value)")
        clauses.append(f"(metric_name = '{metric_name.value}' AND {' AND '.join(requirements)})")
    return " OR ".join(clauses)


class MetricEvent(Base):
    __tablename__ = "metric_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_metric_events_event_id"),
        CheckConstraint(
            f"metric_name IN ({_supported_metric_names_sql()})",
            name="ck_metric_events_metric_name_supported",
        ),
        CheckConstraint(
            "schema_version = 1",
            name="ck_metric_events_schema_version_supported",
        ),
        CheckConstraint(
            "service = lower(service) "
            "AND service !~ '^[[:space:]]' "
            "AND service !~ '[[:space:]]$' "
            "AND char_length(service) > 0",
            name="ck_metric_events_service_normalized",
        ),
        CheckConstraint(
            "jsonb_typeof(tags) = 'object'",
            name="ck_metric_events_tags_object",
        ),
        CheckConstraint(
            _metric_value_semantics_sql(),
            name="ck_metric_events_value_semantics",
        ),
        Index("ix_metric_events_service", "service"),
        Index("ix_metric_events_metric_name", "metric_name"),
        Index("ix_metric_events_event_timestamp", "event_timestamp"),
        Index(
            "ix_metric_events_service_metric_timestamp",
            "service",
            "metric_name",
            "event_timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    service: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
