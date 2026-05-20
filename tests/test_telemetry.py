import sys
from pathlib import Path
from types import SimpleNamespace

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.parquet_span_processor import ParquetSpanProcessor
from src.bench.telemetry import configure_telemetry, decision_context
from src.engine.state import PlayerView
from src.gabm.agent import GABMAgent


class FakeWriter:
    def __init__(self):
        self.rows = []

    def append_decisions(self, rows):
        self.rows.extend(rows)


class FakeSpan:
    start_time = 1_000_000_000
    end_time = 1_250_000_000

    attributes = {
        "gen_ai.request.model": "request-model",
        "gen_ai.response.model": "response-model",
        "gen_ai.provider.name": "ollama",
        "gen_ai.request.temperature": 0.4,
        "gen_ai.request.seed": 123,
        "gen_ai.usage.input_tokens": 10,
        "gen_ai.usage.output_tokens": 3,
        "gen_ai.usage.reasoning.output_tokens": 2,
        "gen_ai.usage.cache_read.input_tokens": 5,
        "gen_ai.response.finish_reasons": ["stop"],
        "gen_ai.response.id": "resp-1",
        "beergame.run_id": "run-1",
        "beergame.game_id": "game-1",
        "beergame.scenario_id": "step",
        "beergame.epoch": 0,
        "beergame.week": 1,
        "beergame.role": "retailer",
        "beergame.parse_ok": True,
        "beergame.parse_strategy": "first_int",
        "beergame.decision_int": 7,
        "beergame.cache_hit": False,
    }


def test_span_to_decision_row_maps_otel_attrs_to_stable_columns():
    writer = FakeWriter()
    ParquetSpanProcessor(writer).on_end(FakeSpan())
    row = writer.rows[0]

    assert row["run_id"] == "run-1"
    assert row["game_id"] == "game-1"
    assert row["model_request"] == "request-model"
    assert row["model_response"] == "response-model"
    assert row["provider"] == "ollama"
    assert row["input_tokens"] == 10
    assert row["output_tokens"] == 3
    assert row["reasoning_tokens"] == 2
    assert row["cache_read_input_tokens"] == 5
    assert row["finish_reason"] == "stop"
    assert row["latency_ms"] == 250
    assert row["parse_ok"] is True
    assert row["decision_int"] == 7


def test_gabm_decision_without_usage_writes_row_with_null_tokens():
    writer = FakeWriter()
    session = configure_telemetry(writer)
    agent = GABMAgent("Retailer")
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions(FakeResponse(usage=None)))
    )
    view = PlayerView(
        role="Retailer",
        week=1,
        inventory=12,
        backlog=0,
        incoming_order=4,
        shipment_received=4,
        last_order_placed=4,
        on_order=8,
    )

    try:
        with decision_context(
            run_id="run-1",
            game_id="game-1",
            scenario_id="step",
            scenario_release="2026-Q2",
            epoch=0,
            week=1,
            role="retailer",
            llm_seed=123,
            cache_hit=False,
        ):
            decision = agent.decide(view)
    finally:
        session.shutdown()

    assert decision == 7
    assert len(writer.rows) == 1
    row = writer.rows[0]
    assert row["run_id"] == "run-1"
    assert row["role"] == "retailer"
    assert row["provider"] == "ollama"
    assert row["model_request"] == agent.model
    assert row["model_response"] == "fake-model"
    assert row["seed_request"] == 123
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    assert row["parse_ok"] is True
    assert row["parse_strategy"] == "strict_int"
    assert row["decision_int"] == 7


def test_gabm_decision_uses_reasoning_when_content_is_empty():
    writer = FakeWriter()
    session = configure_telemetry(writer)
    agent = GABMAgent("Retailer")
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions(
                FakeResponse(usage=None, content="", reasoning="maybe 3\nactually 9")
            )
        )
    )
    view = PlayerView(
        role="Retailer",
        week=1,
        inventory=12,
        backlog=0,
        incoming_order=4,
        shipment_received=4,
        last_order_placed=4,
        on_order=8,
    )

    try:
        with decision_context(
            run_id="run-1",
            game_id="game-1",
            scenario_id="step",
            scenario_release="2026-Q2",
            epoch=0,
            week=1,
            role="retailer",
            llm_seed=123,
            cache_hit=False,
        ):
            decision = agent.decide(view)
    finally:
        session.shutdown()

    assert decision == 9
    assert writer.rows[0]["parse_ok"] is True
    assert writer.rows[0]["parse_strategy"] == "last_line_int"
    assert writer.rows[0]["decision_int"] == 9


def test_gabm_decision_implausible_parse_defaults_zero():
    writer = FakeWriter()
    session = configure_telemetry(writer)
    agent = GABMAgent("Retailer")
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions(
                FakeResponse(usage=None, content="1001", reasoning=None)
            )
        )
    )
    view = PlayerView(
        role="Retailer",
        week=1,
        inventory=12,
        backlog=0,
        incoming_order=4,
        shipment_received=4,
        last_order_placed=4,
        on_order=8,
    )

    try:
        with decision_context(
            run_id="run-1",
            game_id="game-1",
            scenario_id="step",
            scenario_release="2026-Q2",
            epoch=0,
            week=1,
            role="retailer",
            llm_seed=123,
            cache_hit=False,
        ):
            decision = agent.decide(view)
    finally:
        session.shutdown()

    assert decision == 0
    assert writer.rows[0]["parse_ok"] is False
    assert writer.rows[0]["parse_strategy"] == "strict_int"
    assert writer.rows[0]["decision_int"] == 0


def test_gabm_decision_error_writes_error_row_and_defaults_zero():
    writer = FakeWriter()
    session = configure_telemetry(writer)
    agent = GABMAgent("Retailer")
    agent.client = SimpleNamespace(
        chat=SimpleNamespace(completions=RaisingCompletions())
    )
    view = PlayerView(
        role="Retailer",
        week=1,
        inventory=12,
        backlog=0,
        incoming_order=4,
        shipment_received=4,
        last_order_placed=4,
        on_order=8,
    )

    try:
        with decision_context(
            run_id="run-1",
            game_id="game-1",
            scenario_id="step",
            scenario_release="2026-Q2",
            epoch=0,
            week=1,
            role="retailer",
            llm_seed=123,
            cache_hit=False,
        ):
            decision = agent.decide(view)
    finally:
        session.shutdown()

    assert decision == 0
    assert len(writer.rows) == 1
    assert writer.rows[0]["error_type"] == "RuntimeError"
    assert writer.rows[0]["parse_ok"] is False
    assert writer.rows[0]["decision_int"] == 0


class FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class RaisingCompletions:
    def create(self, **kwargs):
        raise RuntimeError("provider unavailable")


class FakeResponse:
    def __init__(self, usage, content="7", reasoning=None):
        self.id = "resp-1"
        self.model = "fake-model"
        self.usage = usage
        self.choices = [
            SimpleNamespace(
                message=SimpleNamespace(content=content, reasoning=reasoning),
                finish_reason="stop",
            )
        ]
