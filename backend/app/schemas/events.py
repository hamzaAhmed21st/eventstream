from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.metrics import METRIC_SPECIFICATIONS, metric_value_contract_description
from app.core.metrics import MetricName as MetricName

MAX_TAGS = 20
MAX_TAG_KEY_LENGTH = 64
MAX_TAG_VALUE_LENGTH = 256


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(
        description="Stable client-generated identity; reuse it when retrying the same event."
    )
    service: str = Field(
        max_length=128,
        description=(
            "NUL-free service name, normalized to lowercase without surrounding whitespace; "
            "maximum 128 characters after normalization."
        ),
    )
    metric_name: MetricName = Field(description="Metric contract applied to value.")
    value: float = Field(
        allow_inf_nan=False,
        strict=True,
        description=metric_value_contract_description(),
    )
    timestamp: datetime = Field(description="Timezone-aware event time; normalized to UTC.")
    tags: dict[str, str] = Field(
        default_factory=dict,
        description="Up to 20 NUL-free string key/value tags.",
    )
    schema_version: int = Field(
        default=1,
        strict=True,
        description="Event schema version; the MVP supports version 1.",
    )

    @field_validator("service", mode="before")
    @classmethod
    def normalize_service(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("service cannot be empty")
        if "\x00" in normalized:
            raise ValueError("service cannot contain NUL characters")
        return normalized

    @field_validator("value")
    @classmethod
    def require_finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        return value

    @model_validator(mode="after")
    def require_metric_value_semantics(self) -> Self:
        specification = METRIC_SPECIFICATIONS[self.metric_name]
        if not specification.minimum <= self.value <= specification.maximum:
            raise ValueError(specification.describe_value(self.metric_name))
        if specification.integral and not self.value.is_integer():
            raise ValueError(specification.describe_value(self.metric_name))
        return self

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(UTC)

    @field_validator("tags", mode="before")
    @classmethod
    def default_null_tags(cls, value: Any) -> Any:
        return {} if value is None else value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > MAX_TAGS:
            raise ValueError(f"tags cannot contain more than {MAX_TAGS} entries")
        for key, tag_value in value.items():
            if not key:
                raise ValueError("tag keys cannot be empty")
            if "\x00" in key:
                raise ValueError("tag keys cannot contain NUL characters")
            if len(key) > MAX_TAG_KEY_LENGTH:
                raise ValueError(f"tag keys cannot exceed {MAX_TAG_KEY_LENGTH} characters")
            if "\x00" in tag_value:
                raise ValueError("tag values cannot contain NUL characters")
            if len(tag_value) > MAX_TAG_VALUE_LENGTH:
                raise ValueError(f"tag values cannot exceed {MAX_TAG_VALUE_LENGTH} characters")
        return value

    @field_validator("schema_version")
    @classmethod
    def require_supported_schema_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("schema_version must be 1")
        return value


class StreamEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: EventCreate
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def normalize_received_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must include a timezone")
        return value.astimezone(UTC)


class EventAccepted(BaseModel):
    event_id: UUID
    status: Literal["accepted"] = "accepted"
    stream_id: str


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: UUID
    service: str
    metric_name: MetricName
    value: float
    timestamp: datetime = Field(validation_alias="event_timestamp")
    tags: dict[str, str]
    schema_version: int
    received_at: datetime
    processed_at: datetime


class EventPage(BaseModel):
    items: list[EventRead]
    page: int
    page_size: int
    total: int


class MetricSummary(BaseModel):
    event_count: int
    min_value: float | None
    max_value: float | None
    average_value: float | None
    sum_value: float | None
    most_recent_value: float | None
    most_recent_timestamp: datetime | None

    @model_validator(mode="after")
    def require_consistent_empty_state(self) -> Self:
        aggregate_values = (
            self.min_value,
            self.max_value,
            self.average_value,
            self.sum_value,
            self.most_recent_value,
            self.most_recent_timestamp,
        )
        if self.event_count == 0 and any(value is not None for value in aggregate_values):
            raise ValueError("empty summaries must have null aggregate values")
        return self
