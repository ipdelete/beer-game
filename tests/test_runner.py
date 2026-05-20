import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.bundle import BundleWriter
from src.bench.runner import run_matrix


def test_run_matrix_writes_cross_product(tmp_path):
    bundle = run_matrix(_matrix_config(), root=tmp_path, run_id="matrix")

    games = _games(bundle)
    decisions = pq.read_table(bundle / "decisions.parquet").to_pylist()
    states = pq.read_table(bundle / "states.parquet").to_pylist()
    manifest = json.loads((bundle / "manifest.json").read_text())

    assert len(games) == 8
    assert len({(g["scenario_id"], g["model"], g["epoch"]) for g in games}) == 8
    assert len(decisions) == 8 * 4
    assert len(states) == 8 * 4
    assert manifest["scenario_ids"] == ["step_a", "constant_b"]
    assert [model["id"] for model in manifest["models"]] == ["mech-a", "mech-b"]


def test_run_matrix_resume_skips_successful_games_and_force_reruns(tmp_path):
    first = run_matrix(_matrix_config(), root=tmp_path, run_id="matrix")
    first_ids = [game["game_id"] for game in _games(first)]

    resumed = run_matrix(_matrix_config(), root=tmp_path, run_id="matrix")
    resumed_games = _games(resumed)

    assert [game["game_id"] for game in resumed_games] == first_ids
    assert len(resumed_games) == 8

    forced = run_matrix(_matrix_config(), root=tmp_path, run_id="matrix", force=True)
    forced_ids = [game["game_id"] for game in _games(forced)]

    assert len(forced_ids) == 8
    assert forced_ids != first_ids


def test_run_matrix_parallel_mechanistic_path(tmp_path):
    bundle = run_matrix(_matrix_config(), root=tmp_path, run_id="parallel", parallel=2)

    assert len(_games(bundle)) == 8
    assert pq.read_table(bundle / "decisions.parquet").num_rows == 8 * 4


def test_bundle_writer_concurrent_game_flushes(tmp_path):
    writer = BundleWriter(tmp_path, run_id="writer")
    writer.start(
        models=[{"id": "mechanistic", "provider": "mechanistic"}],
        scenarios=[_scenario("s")],
        config={
            "active_release": "2026-Q2",
            "run_seed": 1,
            "epochs": 1,
            "models": [{"id": "mechanistic", "provider": "mechanistic"}],
            "scenarios": [_scenario("s")],
        },
        matrix_hash="test",
    )

    def append_game(index: int) -> None:
        game_id = f"game-{index}"
        writer.append_decisions([_decision_row(game_id, i) for i in range(100)])
        writer.append_states([_state_row(game_id, i) for i in range(100)])
        writer.flush_game(game_id)
        writer.append_game(
            {
                "game_id": game_id,
                "run_id": "writer",
                "scenario_id": "s",
                "model": "mechanistic",
                "epoch": index,
                "demand_seed": index,
                "llm_seed": index,
                "started_at": writer.started_at,
                "ended_at": writer.started_at,
                "status": "ok",
                "error": None,
                "demand_hash": "hash",
                "total_cost": 1.0,
                "wall_seconds": 0.0,
            }
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(append_game, range(4)))

    bundle = writer.finish()

    assert pq.read_table(bundle / "decisions.parquet").num_rows == 400
    assert pq.read_table(bundle / "states.parquet").num_rows == 400


def _matrix_config() -> dict:
    return {
        "schema_version": "1.0.0",
        "active_release": "2026-Q2",
        "run_seed": 12345,
        "weeks": 1,
        "epochs": 2,
        "mode": "mechanistic",
        "runner": {"parallel": 1, "persist_traces": False},
        "cache": {"enabled": True},
        "scenarios": [
            _scenario("step_a"),
            {
                "scenario_id": "constant_b",
                "demand_pattern": "constant",
                "params": {"value": 8},
                "weeks": 1,
                "costs": {"holding": 0.5, "backlog": 1.0},
                "scenario_seed": 43,
                "release_date": "2026-Q1",
                "removal_date": None,
            },
        ],
        "models": [
            {"id": "mech-a", "provider": "mechanistic", "model": "mechanistic"},
            {"id": "mech-b", "provider": "mechanistic", "model": "mechanistic"},
        ],
        "telemetry": {"otlp_endpoint": None},
    }


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


def _games(bundle: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (bundle / "games.jsonl").read_text().splitlines()
        if line
    ]


def _decision_row(game_id: str, week: int) -> dict:
    return {
        "run_id": "writer",
        "game_id": game_id,
        "scenario_id": "s",
        "epoch": 0,
        "week": week,
        "role": "retailer",
        "model_request": "mechanistic",
        "model_response": None,
        "provider": "mechanistic",
        "temperature": None,
        "top_p": None,
        "seed_request": 0,
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "cache_read_input_tokens": None,
        "finish_reason": None,
        "response_id": None,
        "latency_ms": None,
        "time_to_first_chunk_ms": None,
        "parse_ok": True,
        "parse_strategy": "mechanistic",
        "decision_int": 4,
        "context_used": None,
        "context_window": None,
        "cache_hit": False,
        "error_type": None,
        "raw_response_ref": None,
    }


def _state_row(game_id: str, week: int) -> dict:
    return {
        "run_id": "writer",
        "game_id": game_id,
        "week": week,
        "role": "retailer",
        "inventory": 12,
        "backlog": 0,
        "order_placed": 4,
        "shipment_received": 4,
        "customer_demand": 4,
        "cost_week": 6.0,
        "cost_cum": 6.0,
    }
