#!/usr/bin/env python3
"""Send deterministic synthetic metric events to an EventStream API."""

from __future__ import annotations

import argparse
import math
import random
import signal
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from types import FrameType
from uuid import UUID

import httpx

METRIC_NAMES = (
    "latency_ms",
    "request_count",
    "error_count",
    "cpu_usage",
    "memory_usage",
)
METRIC_WEIGHTS = (30, 28, 7, 18, 17)
REGIONS = ("us-central", "us-east", "us-west")


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    endpoint: str
    events_per_second: float
    count: int | None
    services: tuple[str, ...]
    seed: int
    request_timeout: float


@dataclass(slots=True)
class Counters:
    accepted: int = 0
    failed: int = 0

    @property
    def attempted(self) -> int:
        return self.accepted + self.failed


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be finite and greater than zero")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def service_list(value: str) -> tuple[str, ...]:
    services = tuple(service.strip() for service in value.split(",") if service.strip())
    if not services:
        raise argparse.ArgumentTypeError("provide at least one nonempty service")
    return services


def parse_args(argv: Sequence[str] | None = None) -> GeneratorConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Send realistic synthetic metrics. Omit --count to continue until "
            "SIGINT or SIGTERM."
        )
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--events-per-second",
        type=positive_float,
        default=10.0,
        help="target request rate (default: %(default)s)",
    )
    parser.add_argument(
        "--count",
        type=positive_int,
        help="stop after this many requests; omit to run until interrupted",
    )
    parser.add_argument(
        "--services",
        type=service_list,
        default=service_list("checkout,catalog,accounts"),
        help="comma-separated service names (default: checkout,catalog,accounts)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="deterministic random seed (default: %(default)s)",
    )
    parser.add_argument(
        "--request-timeout",
        type=positive_float,
        default=5.0,
        help="per-request timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    endpoint = f"{str(args.api_url).rstrip('/')}/api/v1/events"
    return GeneratorConfig(
        endpoint=endpoint,
        events_per_second=float(args.events_per_second),
        count=args.count,
        services=args.services,
        seed=int(args.seed),
        request_timeout=float(args.request_timeout),
    )


def metric_value(metric_name: str, rng: random.Random) -> float:
    if metric_name == "latency_ms":
        value = rng.lognormvariate(4.2, 0.45)
        if rng.random() < 0.03:
            value *= rng.uniform(5.0, 12.0)
        return round(value, 3)
    if metric_name == "request_count":
        return float(rng.randint(1, 40))
    if metric_name == "error_count":
        return float(rng.randint(1, 5))
    if metric_name == "cpu_usage":
        value = rng.uniform(8.0, 75.0)
        if rng.random() < 0.03:
            value = rng.uniform(85.0, 99.0)
        return round(value, 3)
    if metric_name == "memory_usage":
        return round(rng.uniform(20.0, 92.0), 3)
    raise ValueError(f"unsupported metric name: {metric_name}")


def build_event(config: GeneratorConfig, rng: random.Random) -> dict[str, object]:
    metric_name = rng.choices(METRIC_NAMES, weights=METRIC_WEIGHTS, k=1)[0]
    event_id = UUID(int=rng.getrandbits(128), version=4)
    return {
        "event_id": str(event_id),
        "service": rng.choice(config.services),
        "metric_name": metric_name,
        "value": metric_value(metric_name, rng),
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "tags": {
            "environment": "local",
            "generator": "synthetic",
            "region": rng.choice(REGIONS),
        },
        "schema_version": 1,
    }


def wait_until(deadline: float, stop_requested: threading.Event) -> None:
    while not stop_requested.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        stop_requested.wait(timeout=min(remaining, 0.25))


def run(config: GeneratorConfig) -> Counters:
    rng = random.Random(config.seed)
    counters = Counters()
    stop_requested = threading.Event()

    def request_stop(_signum: int, _frame: FrameType | None) -> None:
        stop_requested.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    interval = 1.0 / config.events_per_second
    next_request_at = time.monotonic()
    print(
        f"Sending events to {config.endpoint} at up to "
        f"{config.events_per_second:g} events/second (seed={config.seed})."
    )

    with httpx.Client(timeout=config.request_timeout) as client:
        while not stop_requested.is_set() and (
            config.count is None or counters.attempted < config.count
        ):
            wait_until(next_request_at, stop_requested)
            if stop_requested.is_set():
                break

            payload = build_event(config, rng)
            try:
                response = client.post(config.endpoint, json=payload)
                if response.status_code == httpx.codes.ACCEPTED:
                    counters.accepted += 1
                else:
                    counters.failed += 1
                    detail = response.text.replace("\n", " ")[:200]
                    print(
                        f"Request failed: status={response.status_code} body={detail!r}",
                        file=sys.stderr,
                    )
            except httpx.RequestError as exc:
                counters.failed += 1
                print(f"Request failed: {exc}", file=sys.stderr)

            next_request_at += interval

    print(
        "Synthetic event run finished: "
        f"attempted={counters.attempted} accepted={counters.accepted} "
        f"failed={counters.failed}"
    )
    return counters


def main(argv: Sequence[str] | None = None) -> int:
    config = parse_args(argv)
    counters = run(config)
    return 0 if counters.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
