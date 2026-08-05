from __future__ import annotations

import argparse

import pytest
from scripts.generate_events import positive_float


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf"])
def test_positive_float_rejects_nonpositive_or_nonfinite_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        positive_float(value)


def test_positive_float_accepts_finite_positive_value() -> None:
    assert positive_float("2.5") == 2.5
