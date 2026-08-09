from __future__ import annotations

import argparse
import random
from uuid import UUID

import pytest
from scripts import generate_events
from scripts.generate_events import GeneratorConfig, build_event, positive_float


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf"])
def test_positive_float_rejects_nonpositive_or_nonfinite_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        positive_float(value)


def test_positive_float_accepts_finite_positive_value() -> None:
    assert positive_float("2.5") == 2.5


def test_repeated_seeded_runs_keep_content_but_use_fresh_event_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_ids = iter(
        (
            UUID("79b8d3dc-2192-4a55-b0ce-4ef371ba6f5b"),
            UUID("f1b8928f-fad9-49ce-8b92-bd6eebc696d5"),
        )
    )
    monkeypatch.setattr(generate_events, "uuid4", lambda: next(event_ids))
    config = GeneratorConfig(
        endpoint="http://localhost:8000/api/v1/events",
        events_per_second=10,
        count=1,
        services=("checkout", "catalog"),
        seed=42,
        request_timeout=5,
    )

    first = build_event(config, random.Random(config.seed))
    second = build_event(config, random.Random(config.seed))

    assert first["event_id"] != second["event_id"]
    seeded_fields = {"service", "metric_name", "value", "tags", "schema_version"}
    assert {field: first[field] for field in seeded_fields} == {
        field: second[field] for field in seeded_fields
    }
