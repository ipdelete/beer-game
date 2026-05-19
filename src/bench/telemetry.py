"""OpenTelemetry setup and context helpers for Beer Game benchmarks."""

from __future__ import annotations

import contextlib
import contextvars
import os
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import Tracer

# OTel GenAI conventions are still Development. Snapshotting to stable Beer Game
# columns happens in ParquetSpanProcessor through this single mapping point.
OTEL_TO_COLUMN = {
    "gen_ai.request.model": "model_request",
    "gen_ai.response.model": "model_response",
    "gen_ai.provider.name": "provider",
    "gen_ai.request.temperature": "temperature",
    "gen_ai.request.top_p": "top_p",
    "gen_ai.request.seed": "seed_request",
    "gen_ai.usage.input_tokens": "input_tokens",
    "gen_ai.usage.output_tokens": "output_tokens",
    "gen_ai.usage.reasoning.output_tokens": "reasoning_tokens",
    "gen_ai.usage.cache_read.input_tokens": "cache_read_input_tokens",
    "gen_ai.response.finish_reasons": "finish_reason",
    "gen_ai.response.id": "response_id",
    "gen_ai.response.time_to_first_chunk": "time_to_first_chunk_ms",
}


@dataclass(frozen=True)
class DecisionContext:
    run_id: str
    game_id: str
    scenario_id: str
    scenario_release: str
    epoch: int
    week: int
    role: str
    llm_seed: int | None
    cache_hit: bool = False
    context_used: int | None = None
    context_window: int | None = None


@dataclass
class TelemetrySession:
    provider: TracerProvider
    token: contextvars.Token[Tracer]

    def shutdown(self) -> None:
        self.provider.force_flush(timeout_millis=5000)
        self.provider.shutdown()
        _tracer_var.reset(self.token)


_tracer_var: contextvars.ContextVar[Tracer] = contextvars.ContextVar(
    "beergame_tracer", default=trace.get_tracer("beer-game")
)
_decision_context_var: contextvars.ContextVar[DecisionContext | None] = (
    contextvars.ContextVar("beergame_decision_context", default=None)
)


def configure_telemetry(bundle_writer=None) -> TelemetrySession:
    """Create a per-run tracer provider and bind it to the current context."""

    from src.bench.parquet_span_processor import ParquetSpanProcessor

    provider = TracerProvider()
    if bundle_writer is not None:
        provider.add_span_processor(ParquetSpanProcessor(bundle_writer))

    otlp_endpoint = os.getenv("BEERGAME_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise RuntimeError(
                "BEERGAME_OTLP_ENDPOINT requires "
                "opentelemetry-exporter-otlp-proto-http"
            ) from exc
        provider.add_span_processor(
            SimpleSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )

    tracer = provider.get_tracer("beer-game")
    token = _tracer_var.set(tracer)
    return TelemetrySession(provider=provider, token=token)


def get_tracer() -> Tracer:
    """Return the tracer bound to the current benchmark context."""

    return _tracer_var.get()


def get_decision_context() -> DecisionContext | None:
    """Return the active Beer Game decision context, if any."""

    return _decision_context_var.get()


@contextlib.contextmanager
def decision_context(**kwargs: Any) -> Iterator[DecisionContext]:
    """Set Beer Game attributes for one decision call."""

    ctx = DecisionContext(**kwargs)
    token = _decision_context_var.set(ctx)
    try:
        yield ctx
    finally:
        _decision_context_var.reset(token)


def provider_from_endpoint(endpoint: str) -> str:
    """Infer the GenAI provider/runtime from an OpenAI-compatible endpoint."""

    parsed = urlparse(endpoint)
    host = parsed.hostname or ""
    if "localhost" in host or host == "127.0.0.1":
        if parsed.port == 11434:
            return "ollama"
        return "openai-compatible"
    if "openai.com" in host:
        return "openai"
    if "vllm" in host:
        return "vllm"
    return "openai-compatible"


def server_attrs(endpoint: str) -> dict[str, str | int]:
    """Return server.address and server.port attrs when derivable."""

    parsed = urlparse(endpoint)
    attrs: dict[str, str | int] = {}
    if parsed.hostname:
        attrs["server.address"] = parsed.hostname
    if parsed.port:
        attrs["server.port"] = parsed.port
    return attrs
