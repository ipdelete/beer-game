import sys
from pathlib import Path

import duckdb
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.bundle import demand_hash
from src.bench.config import load_config
from src.bench.demand import GENERATORS, materialize_demand
from src.bench.run import run_bundle


@pytest.mark.parametrize(
    ("pattern", "params"),
    [
        ("constant", {"value": 8}),
        ("step", {"low": 4, "high": 8, "step_week": 5}),
        ("ramp", {"start": 4, "end": 12, "start_week": 3, "end_week": 10}),
        ("sinusoid", {"mean": 8, "amplitude": 3, "period_weeks": 13}),
        ("bounded_random", {"low": 4, "high": 12}),
    ],
)
def test_generators_return_integer_arrays(pattern, params):
    demand = GENERATORS[pattern](12, params, np.random.default_rng(1))

    assert demand.shape == (12,)
    assert np.issubdtype(demand.dtype, np.integer)
    assert (demand >= 0).all()


def test_classic_step_and_constant_hashes_are_preserved():
    step = materialize_demand(
        _scenario("step", {"low": 4, "high": 8, "step_week": 5}, weeks=36),
        run_seed=12345,
        epoch=0,
    )
    constant = materialize_demand(
        _scenario("constant", {"value": 8}, weeks=1), run_seed=12345, epoch=0
    )

    assert demand_hash(step.tolist()) == demand_hash([4, 4, 4, 4, *([8] * 32)])
    assert demand_hash(constant.tolist()) == demand_hash([8])


def test_bounded_random_seed_reproducibility_and_epoch_variation():
    scenario = _scenario("bounded_random", {"low": 4, "high": 12}, weeks=20)

    first = materialize_demand(scenario, run_seed=12345, epoch=0)
    second = materialize_demand(scenario, run_seed=12345, epoch=0)
    other_epoch = materialize_demand(scenario, run_seed=12345, epoch=1)

    assert first.tolist() == second.tolist()
    assert first.tolist() != other_epoch.tolist()


@settings(max_examples=10)
@given(
    low=st.integers(min_value=0, max_value=10),
    width=st.integers(min_value=1, max_value=10),
)
def test_bounded_random_variance_matches_discrete_uniform(low, width):
    high = low + width
    demand = GENERATORS["bounded_random"](
        10_000, {"low": low, "high": high}, np.random.default_rng(5)
    )
    expected = (((high - low + 1) ** 2) - 1) / 12

    assert abs(float(np.var(demand)) - expected) / expected < 0.05


def test_config_validation_rejects_bad_demand_params(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("""
schema_version: "1.0.0"
active_release: "2026-Q3"
run_seed: 1
weeks: 1
epochs: 1
mode: mechanistic
runner: {parallel: 1, persist_traces: false}
cache: {enabled: true}
scenarios:
  - scenario_id: bad
    demand_pattern: bounded_random
    params: {low: 10, high: 4}
    weeks: 1
    costs: {holding: 0.5, backlog: 1.0}
    scenario_seed: 1
    release_date: "2026-Q3"
    removal_date: null
models:
  - id: mechanistic
    provider: mechanistic
    model: mechanistic
telemetry: {}
""")

    with pytest.raises(ValueError, match="high"):
        load_config(path)


def test_runtime_uses_materialized_demand_for_states_and_game_hash(tmp_path):
    config = {
        "schema_version": "1.0.0",
        "active_release": "2026-Q3",
        "run_seed": 12345,
        "weeks": 6,
        "epochs": 2,
        "mode": "mechanistic",
        "runner": {"parallel": 1, "persist_traces": False},
        "cache": {"enabled": True},
        "scenarios": [_scenario("bounded_random", {"low": 4, "high": 12}, weeks=6)],
        "models": [
            {"id": "mechanistic", "provider": "mechanistic", "model": "mechanistic"}
        ],
        "telemetry": {"otlp_endpoint": None},
    }
    bundle = run_bundle(config=config, root=tmp_path, run_id="random")
    expected = materialize_demand(config["scenarios"][0], config["run_seed"], epoch=1)

    with duckdb.connect() as con:
        states = con.execute(
            "SELECT customer_demand FROM read_parquet(?) WHERE role = 'retailer' "
            "AND game_id = (SELECT game_id FROM read_json_auto(?) WHERE epoch = 1)",
            [str(bundle / "states.parquet"), str(bundle / "games.jsonl")],
        ).fetchall()
        game_hash = con.execute(
            "SELECT demand_hash FROM read_json_auto(?) WHERE epoch = 1",
            [str(bundle / "games.jsonl")],
        ).fetchone()[0]

    assert [row[0] for row in states] == expected.tolist()
    assert game_hash == demand_hash(expected.tolist())


def _scenario(pattern: str, params: dict, *, weeks: int = 12) -> dict:
    return {
        "scenario_id": f"{pattern}_test",
        "demand_pattern": pattern,
        "params": params,
        "weeks": weeks,
        "costs": {"holding": 0.5, "backlog": 1.0},
        "scenario_seed": 42,
        "release_date": "2026-Q3",
        "removal_date": None,
    }
