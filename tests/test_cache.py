import sys
from pathlib import Path
from types import SimpleNamespace

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.cache import CacheKey, ResponseCache
from src.bench.telemetry import configure_telemetry, decision_context
from src.engine.state import PlayerView
from src.gabm.agent import GABMAgent, configure_cache


def test_cache_key_changes_for_correctness_fields():
    base = _cache_key()
    variants = [
        _cache_key(llm_seed=2),
        _cache_key(scenario_params_hash="params-b"),
        _cache_key(prompt_version="prompt-b"),
        _cache_key(demand_hash="demand-b"),
    ]

    assert all(base.hash() != variant.hash() for variant in variants)


def test_response_cache_fetch_store_and_refresh(tmp_path):
    key = _cache_key()
    cache = ResponseCache(tmp_path)
    assert cache.fetch(key) is None

    cache.store(key, {"model": "m", "choices": []})
    assert cache.fetch(key)["model"] == "m"

    assert ResponseCache(tmp_path, refresh=True).fetch(key) is None
    disabled = ResponseCache(tmp_path, enabled=False)
    disabled.store(_cache_key(model="other"), {"model": "other"})
    assert disabled.fetch(key) is None


def test_response_cache_uses_env_root(tmp_path, monkeypatch):
    monkeypatch.setenv("BEERGAME_CACHE_DIR", str(tmp_path))
    cache = ResponseCache()
    key = _cache_key(model="mistral:latest")
    cache.store(key, {"model": "m", "choices": []})

    assert next((tmp_path / "generate").glob("mistral_latest/*.json")).exists()


def test_gabm_decision_reuses_successful_cached_response(tmp_path):
    writer = FakeWriter()
    session = configure_telemetry(writer)
    completions = CountingCompletions()
    agent = GABMAgent("Retailer")
    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    configure_cache(ResponseCache(tmp_path))
    view = _view()

    try:
        for _ in range(2):
            with decision_context(
                run_id="run-1",
                game_id="game-1",
                scenario_id="step",
                scenario_release="2026-Q2",
                epoch=0,
                week=1,
                role="retailer",
                llm_seed=123,
                scenario_params_hash="params",
                demand_hash="demand",
                prompt_version="prompt",
                cache_hit=False,
            ):
                assert agent.decide(view) == 7
    finally:
        session.shutdown()
        configure_cache(None)

    assert completions.calls == 1
    assert [row["cache_hit"] for row in writer.rows] == [False, True]
    assert [row["input_tokens"] for row in writer.rows] == [10, 10]
    assert [row["output_tokens"] for row in writer.rows] == [3, 3]


def test_gabm_decision_does_not_cache_failed_parse(tmp_path):
    writer = FakeWriter()
    session = configure_telemetry(writer)
    completions = CountingCompletions(content="1001")
    agent = GABMAgent("Retailer")
    agent.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    configure_cache(ResponseCache(tmp_path))
    view = _view()

    try:
        for _ in range(2):
            with decision_context(
                run_id="run-1",
                game_id="game-1",
                scenario_id="step",
                scenario_release="2026-Q2",
                epoch=0,
                week=1,
                role="retailer",
                llm_seed=123,
                scenario_params_hash="params",
                demand_hash="demand",
                prompt_version="prompt",
                cache_hit=False,
            ):
                assert agent.decide(view) == 0
    finally:
        session.shutdown()
        configure_cache(None)

    assert completions.calls == 2
    assert [row["cache_hit"] for row in writer.rows] == [False, False]


def _cache_key(**overrides) -> CacheKey:
    values = {
        "base_url": "http://localhost:11434/v1",
        "model": "mistral:latest",
        "temperature": 0.4,
        "top_p": None,
        "llm_seed": 1,
        "messages": [{"role": "user", "content": "order?"}],
        "scenario_id": "step",
        "scenario_params_hash": "params-a",
        "demand_hash": "demand-a",
        "prompt_version": "prompt-a",
        "epoch": 0,
    }
    values.update(overrides)
    return CacheKey(**values)


def _view() -> PlayerView:
    return PlayerView(
        role="Retailer",
        week=1,
        inventory=12,
        backlog=0,
        incoming_order=4,
        shipment_received=4,
        last_order_placed=4,
        on_order=8,
    )


class FakeWriter:
    def __init__(self):
        self.rows = []

    def append_decisions(self, rows):
        self.rows.extend(rows)


class CountingCompletions:
    def __init__(self, content="7"):
        self.content = content
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            id=f"resp-{self.calls}",
            model="fake-model",
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=3,
                completion_tokens_details=SimpleNamespace(reasoning_tokens=1),
                prompt_tokens_details=SimpleNamespace(cached_tokens=2),
            ),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content, reasoning=None),
                    finish_reason="stop",
                )
            ],
        )
