from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class MetricName(StrEnum):
    LATENCY_MS = "latency_ms"
    REQUEST_COUNT = "request_count"
    ERROR_COUNT = "error_count"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"


@dataclass(frozen=True, slots=True)
class MetricSpecification:
    unit: str
    minimum: float
    maximum: float
    integral: bool = False

    def describe_value(self, metric_name: MetricName) -> str:
        value_kind = "whole-number " if self.integral else ""
        return (
            f"{metric_name.value} accepts {value_kind}{self.unit} values from "
            f"{self.minimum:g} through {self.maximum:g}, inclusive"
        )


METRIC_SPECIFICATIONS: Final[Mapping[MetricName, MetricSpecification]] = MappingProxyType(
    {
        MetricName.LATENCY_MS: MetricSpecification(
            unit="milliseconds",
            minimum=0,
            maximum=86_400_000,
        ),
        MetricName.REQUEST_COUNT: MetricSpecification(
            unit="count",
            minimum=0,
            maximum=1_000_000_000,
            integral=True,
        ),
        MetricName.ERROR_COUNT: MetricSpecification(
            unit="count",
            minimum=0,
            maximum=1_000_000_000,
            integral=True,
        ),
        MetricName.CPU_USAGE: MetricSpecification(
            unit="percent",
            minimum=0,
            maximum=100,
        ),
        MetricName.MEMORY_USAGE: MetricSpecification(
            unit="percent",
            minimum=0,
            maximum=100,
        ),
    }
)


def metric_value_contract_description() -> str:
    return "; ".join(
        specification.describe_value(metric_name)
        for metric_name, specification in METRIC_SPECIFICATIONS.items()
    )
