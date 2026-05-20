"""Reducers for aggregating metric values across epochs."""

from __future__ import annotations

import numpy as np


def mean(values: list[float]) -> float:
    """Arithmetic mean of values."""

    return float(np.mean(values)) if values else 0.0


def std(values: list[float]) -> float:
    """Sample standard deviation, or 0.0 for fewer than two values."""

    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def stderr(values: list[float]) -> float:
    """Standard error of the mean, or 0.0 for fewer than two values."""

    if len(values) < 2:
        return 0.0
    return float(np.std(values, ddof=1) / np.sqrt(len(values)))


def bootstrap_stderr(
    values: list[float], num_samples: int = 1000, seed: int = 0
) -> float:
    """Inspect-style standard deviation of bootstrap means.

    Uses `np.std(..., ddof=0)` on the bootstrap mean distribution to match
    Inspect AI's reference implementation.
    """

    if len(values) < 2:
        return 0.0
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(num_samples, len(values)), replace=True)
    return float(np.std(samples.mean(axis=1), ddof=0))
