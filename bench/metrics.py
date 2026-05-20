"""Compatibility wrapper for `bench.metrics` imports."""

from src.bench.metrics import (
    bullwhip_ratio,
    list_metrics,
    metric,
    parse_success_rate,
    recovery_time,
    run_metrics,
    total_cost,
)

__all__ = [
    "bullwhip_ratio",
    "list_metrics",
    "metric",
    "parse_success_rate",
    "recovery_time",
    "run_metrics",
    "total_cost",
]
