"""OpenTelemetry span processor that appends Beer Game decision rows."""

from __future__ import annotations

from typing import Any

from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

from src.bench.bundle import DECISIONS_SCHEMA


class ParquetSpanProcessor(SpanProcessor):
    """Synchronously map completed spans to `decisions.parquet` rows.

    This processor intentionally appends rows inline from `on_end()`. Bundle
    finalization must flush/shutdown the owning tracer provider before writing
    Parquet so no completed span is missed.
    """

    def __init__(self, bundle_writer):
        self.bundle_writer = bundle_writer

    def on_start(self, span, parent_context=None) -> None:  # noqa: D102
        return None

    def on_end(self, span: ReadableSpan) -> None:  # noqa: D102
        self.bundle_writer.append_decisions([span_to_decision_row(span)])

    def shutdown(self) -> None:  # noqa: D102
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: D102
        return True


def span_to_decision_row(span: ReadableSpan) -> dict[str, Any]:
    """Convert one completed OTel span into a stable decision row."""

    from src.bench.telemetry import OTEL_TO_COLUMN

    attrs = dict(getattr(span, "attributes", {}) or {})
    row = {field.name: None for field in DECISIONS_SCHEMA}

    for attr_name, column_name in OTEL_TO_COLUMN.items():
        value = attrs.get(attr_name)
        if value is None:
            continue
        row[column_name] = _convert_value(attr_name, value)

    for attr_name, column_name in _BEERGAME_TO_COLUMN.items():
        value = attrs.get(attr_name)
        if value is not None:
            row[column_name] = value

    row["latency_ms"] = _latency_ms(span)
    error_type = attrs.get("error.type")
    if error_type is not None:
        row["error_type"] = error_type

    return row


_BEERGAME_TO_COLUMN = {
    "beergame.run_id": "run_id",
    "beergame.game_id": "game_id",
    "beergame.scenario_id": "scenario_id",
    "beergame.epoch": "epoch",
    "beergame.week": "week",
    "beergame.role": "role",
    "beergame.context_used": "context_used",
    "beergame.context_window": "context_window",
    "beergame.parse_ok": "parse_ok",
    "beergame.parse_strategy": "parse_strategy",
    "beergame.decision_int": "decision_int",
    "beergame.cache_hit": "cache_hit",
}


def _convert_value(attr_name: str, value: Any) -> Any:
    if attr_name == "gen_ai.response.finish_reasons":
        if isinstance(value, (list, tuple)):
            return value[0] if value else None
        return value
    if attr_name == "gen_ai.response.time_to_first_chunk":
        return int(value * 1000)
    return value


def _latency_ms(span: ReadableSpan) -> int | None:
    start_time = getattr(span, "start_time", None)
    end_time = getattr(span, "end_time", None)
    if start_time is None or end_time is None:
        return None
    return max(0, int((end_time - start_time) / 1_000_000))
