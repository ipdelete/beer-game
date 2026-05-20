import json
import sys
from pathlib import Path

import numpy as np
from click.testing import CliRunner

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from bench.cli.main import bench
from src.bench.bundle import BundleWriter
from src.bench.metrics import HIGHER_IS_BETTER, LOWER_IS_BETTER, metric_direction
from src.bench.query import open_bundle
from src.bench.significance import (
    compare_bundle,
    paired_bootstrap,
    paired_metric_values,
)


def test_paired_bootstrap_identical_inputs_are_not_significant():
    result = paired_bootstrap(
        [1, 2, 3],
        [1, 2, 3],
        metric_name="m",
        baseline_name="a",
        challenger_name="b",
        num_samples=500,
    )

    assert result.diff == 0
    assert result.p_value == 1.0
    assert result.significant is False
    assert result.better == "none"


def test_paired_bootstrap_constant_shift_is_significant():
    result = paired_bootstrap(
        [10, 11, 12, 13],
        [7, 8, 9, 10],
        metric_name="total_cost",
        baseline_name="base",
        challenger_name="challenger",
        num_samples=500,
        direction=LOWER_IS_BETTER,
    )

    assert result.diff == -3
    assert result.ci_high < 0
    assert result.significant is True
    assert result.better == "challenger"


def test_paired_bootstrap_shifted_normal_is_deterministic_and_directional():
    rng = np.random.default_rng(7)
    baseline = rng.normal(0, 1, size=30).tolist()
    challenger = (np.asarray(baseline) + 0.4).tolist()

    first = paired_bootstrap(
        baseline,
        challenger,
        metric_name="score",
        baseline_name="base",
        challenger_name="challenger",
        num_samples=1000,
        seed=99,
        direction=HIGHER_IS_BETTER,
    )
    second = paired_bootstrap(
        baseline,
        challenger,
        metric_name="score",
        baseline_name="base",
        challenger_name="challenger",
        num_samples=1000,
        seed=99,
        direction=HIGHER_IS_BETTER,
    )

    assert first == second
    assert 0.35 < first.diff < 0.45
    assert first.significant is True
    assert first.better == "challenger"


def test_metric_direction_defaults_and_parse_override():
    assert metric_direction("total_cost") == LOWER_IS_BETTER
    assert metric_direction("parse_success_rate") == HIGHER_IS_BETTER


def test_paired_metric_values_drop_missing_cells(tmp_path):
    bundle = _comparison_bundle(tmp_path, missing_challenger=True)
    con = open_bundle(bundle)

    baseline, challenger, warnings = paired_metric_values(
        con, "total_cost", baseline="base", challenger="better"
    )

    assert len(baseline) == len(challenger) == 3
    assert any("unpaired cells" in warning for warning in warnings)


def test_compare_bundle_returns_results_and_warnings(tmp_path):
    bundle = _comparison_bundle(tmp_path)
    con = open_bundle(bundle)

    results, warnings = compare_bundle(
        con,
        baseline="base",
        challenger="better",
        metric_names=["total_cost"],
        num_samples=500,
    )

    assert warnings == []
    assert len(results) == 1
    assert results[0].metric == "total_cost"
    assert results[0].better == "better"


def test_bench_compare_table_and_json(tmp_path):
    bundle = _comparison_bundle(tmp_path)
    runner = CliRunner()

    table = runner.invoke(
        bench,
        [
            "compare",
            str(bundle),
            "--baseline",
            "base",
            "--challenger",
            "better",
            "--metric",
            "total_cost",
            "--num-samples",
            "500",
        ],
    )

    assert table.exit_code == 0, table.output
    assert "total_cost" in table.output
    assert "better" in table.output

    as_json = runner.invoke(
        bench,
        [
            "compare",
            str(bundle),
            "--baseline",
            "base",
            "--challenger",
            "better",
            "--metric",
            "total_cost",
            "--format",
            "json",
        ],
    )

    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output)
    assert payload["results"][0]["metric"] == "total_cost"
    assert payload["results"][0]["better"] == "better"


def _comparison_bundle(tmp_path: Path, *, missing_challenger: bool = False) -> Path:
    writer = BundleWriter(tmp_path, run_id="compare")
    scenarios = [_scenario("s1"), _scenario("s2")]
    models = [
        {"id": "base", "provider": "mechanistic", "model": "mechanistic"},
        {"id": "better", "provider": "mechanistic", "model": "mechanistic"},
    ]
    writer.start(
        models=models,
        scenarios=scenarios,
        config={
            "active_release": "2026-Q2",
            "run_seed": 1,
            "epochs": 2,
            "models": models,
            "scenarios": scenarios,
        },
        matrix_hash="test",
    )
    for scenario in scenarios:
        for epoch in range(2):
            for model in models:
                if (
                    missing_challenger
                    and model["id"] == "better"
                    and scenario["scenario_id"] == "s2"
                    and epoch == 1
                ):
                    continue
                cost = 10 + epoch + (0 if scenario["scenario_id"] == "s1" else 2)
                if model["id"] == "better":
                    cost -= 3
                _write_game(writer, scenario["scenario_id"], model["id"], epoch, cost)
    return writer.finish()


def _write_game(
    writer: BundleWriter, scenario_id: str, model: str, epoch: int, cost: float
) -> None:
    game_id = f"{scenario_id}-{model}-{epoch}"
    writer.append_states(
        [
            {
                "run_id": writer.run_id,
                "game_id": game_id,
                "week": 1,
                "role": "retailer",
                "inventory": 0,
                "backlog": 0,
                "order_placed": 0,
                "shipment_received": 0,
                "customer_demand": 4,
                "cost_week": cost,
                "cost_cum": cost,
            }
        ]
    )
    writer.append_decisions(
        [
            {
                "run_id": writer.run_id,
                "game_id": game_id,
                "scenario_id": scenario_id,
                "epoch": epoch,
                "week": 1,
                "role": "retailer",
                "model_request": model,
                "model_response": model,
                "provider": "test",
                "temperature": None,
                "top_p": None,
                "seed_request": 1,
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "cache_read_input_tokens": None,
                "finish_reason": "stop",
                "response_id": game_id,
                "latency_ms": None,
                "time_to_first_chunk_ms": None,
                "parse_ok": True,
                "parse_strategy": "strict_int",
                "decision_int": 1,
                "context_used": None,
                "context_window": None,
                "cache_hit": False,
                "error_type": None,
                "raw_response_ref": None,
            }
        ]
    )
    writer.flush_game(game_id)
    writer.append_game(
        {
            "game_id": game_id,
            "run_id": writer.run_id,
            "scenario_id": scenario_id,
            "model": model,
            "epoch": epoch,
            "demand_seed": epoch + (0 if scenario_id == "s1" else 100),
            "llm_seed": 1,
            "started_at": writer.started_at,
            "ended_at": writer.started_at,
            "status": "ok",
            "error": None,
            "demand_hash": "hash",
            "total_cost": cost,
            "wall_seconds": 0.0,
        }
    )


def _scenario(scenario_id: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "demand_pattern": "step",
        "params": {"low": 4, "high": 8, "step_week": 5},
        "weeks": 1,
        "costs": {"holding": 0.5, "backlog": 1.0},
        "scenario_seed": 42,
        "release_date": "2026-Q1",
        "removal_date": None,
    }
