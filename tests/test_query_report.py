import json
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.bundle import BundleWriter, ROLE_NAMES
from src.bench.query import open_bundle, open_bundles
from src.bench.report import main as report_main
from src.bench.run import run_bundle
from src.bench.runner import run_matrix
from tests.test_runner import _matrix_config

EXAMPLE_BUNDLE = Path("tests/fixtures/minimal.eval")


def test_open_bundle_registers_all_canonical_views():
    con = open_bundle(EXAMPLE_BUNDLE)

    assert con.execute("SELECT count(*) FROM manifest").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM scenarios").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM games").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM decisions").fetchone()[0] >= 1
    assert con.execute("SELECT count(*) FROM states").fetchone()[0] >= 1


def test_open_bundles_adds_bundle_id_to_unioned_views(tmp_path):
    _write_bundle(tmp_path, "one", extra_scenario_field=False)
    _write_bundle(tmp_path, "two", extra_scenario_field=True)

    con = open_bundles(str(tmp_path / "*.eval"))

    assert con.execute("SELECT count(*) FROM games").fetchone()[0] == 2
    assert con.execute(
        "SELECT DISTINCT bundle_id FROM decisions ORDER BY 1"
    ).fetchall() == [
        ("one",),
        ("two",),
    ]
    assert (
        con.execute(
            "SELECT count(*) FROM scenarios WHERE extra_note IS NOT NULL"
        ).fetchone()[0]
        == 1
    )


def test_report_prints_summary_tokens_and_latency(capsys, tmp_path):
    bundle_path = _write_bundle(tmp_path, "report")

    report_main([str(bundle_path)])

    output = capsys.readouterr().out
    assert "Bundle:" in output
    assert "Wall time:" in output
    assert "Models:      test-model" in output
    assert "Tokens by role (model: test-model)" in output
    assert "retailer" in output
    assert "10" in output
    assert "Latency by role (model: test-model, mean / p95 in ms)" in output
    assert "102" in output
    assert "Parse strategies (model: test-model)" in output
    assert "strict_int" in output
    assert "100.0%" in output
    assert "Metrics" in output
    assert "total_cost" in output


def test_report_handles_null_token_and_latency_columns(capsys):
    report_main([str(EXAMPLE_BUNDLE)])

    output = capsys.readouterr().out
    assert "Tokens by role (model: example-model)" in output
    assert "n/a" in output
    assert "Latency by role (model: example-model, mean / p95 in ms)" in output
    assert "Parse strategies" in output


def test_report_prints_reduced_metrics_for_multiple_epochs(capsys, tmp_path):
    bundle_path = run_bundle(turns=6, root=tmp_path, run_id="epochs", epochs=3)

    report_main([str(bundle_path)])

    output = capsys.readouterr().out
    assert "Metrics" in output
    assert "+/-" in output
    assert "(n=3)" in output


def test_report_prints_matrix_for_multi_model_multi_scenario_bundle(capsys, tmp_path):
    bundle_path = run_matrix(_matrix_config(), root=tmp_path, run_id="matrix-report")

    report_main([str(bundle_path)])

    output = capsys.readouterr().out
    assert "Matrix: 2 scenarios x 2 models x 2 epochs" in output
    assert "constant_b" in output
    assert "mech-a" in output


def test_module_entrypoint_runs_report():
    result = subprocess.run(
        [sys.executable, "-m", "src.bench.report", str(EXAMPLE_BUNDLE)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Bundle:" in result.stdout
    assert "Tokens by role" in result.stdout
    assert "Latency by role" in result.stdout
    assert "Metrics" in result.stdout


def _write_bundle(
    tmp_path: Path, run_id: str, *, extra_scenario_field: bool = False
) -> Path:
    scenario = {
        "scenario_id": "step_4_8_2w",
        "demand_pattern": "step",
        "params": {"low": 4, "high": 8, "step_week": 2},
        "weeks": 2,
        "costs": {"holding": 0.5, "backlog": 1.0},
        "scenario_seed": 42,
        "release_date": "2026-Q2",
        "removal_date": None,
    }
    model = {
        "id": "test-model",
        "provider": "test",
        "endpoint": None,
        "temperature": None,
        "top_p": None,
    }
    writer = BundleWriter(tmp_path, run_id=run_id)
    writer.start(
        models=[model],
        scenarios=[scenario],
        config={
            "active_release": "2026-Q2",
            "run_seed": 123,
            "weeks": 2,
            "epochs": 1,
        },
    )
    writer.append_game(
        {
            "game_id": f"{run_id}-game",
            "run_id": run_id,
            "scenario_id": scenario["scenario_id"],
            "model": model["id"],
            "epoch": 0,
            "demand_seed": 1,
            "llm_seed": 2,
            "started_at": writer.started_at,
            "ended_at": writer.started_at,
            "status": "ok",
            "error": None,
            "demand_hash": "hash",
            "total_cost": 12.0,
            "wall_seconds": 0.0,
        }
    )
    writer.append_decisions(_decision_rows(run_id, f"{run_id}-game"))
    writer.append_states(_state_rows(run_id, f"{run_id}-game"))
    bundle_path = writer.finish()

    if extra_scenario_field:
        scenario["extra_note"] = "schema drift"
        (bundle_path / "scenarios.jsonl").write_text(json.dumps(scenario) + "\n")

    return bundle_path


def _decision_rows(run_id: str, game_id: str) -> list[dict]:
    rows = []
    for role_index, role in enumerate(ROLE_NAMES):
        for week in (1, 2):
            rows.append(
                {
                    "run_id": run_id,
                    "game_id": game_id,
                    "scenario_id": "step_4_8_2w",
                    "epoch": 0,
                    "week": week,
                    "role": role,
                    "model_request": "test-model",
                    "model_response": "test-model",
                    "provider": "test",
                    "temperature": None,
                    "top_p": None,
                    "seed_request": 2,
                    "input_tokens": 10 + role_index,
                    "output_tokens": 2 + role_index,
                    "reasoning_tokens": None,
                    "cache_read_input_tokens": None,
                    "finish_reason": "stop",
                    "response_id": f"{role}-{week}",
                    "latency_ms": 100 + (role_index * 10) + week,
                    "time_to_first_chunk_ms": None,
                    "parse_ok": True,
                    "parse_strategy": "strict_int",
                    "decision_int": 4,
                    "context_used": None,
                    "context_window": None,
                    "cache_hit": False,
                    "error_type": None,
                    "raw_response_ref": None,
                }
            )
    return rows


def _state_rows(run_id: str, game_id: str) -> list[dict]:
    rows = []
    for role in ROLE_NAMES:
        for week in (1, 2):
            rows.append(
                {
                    "run_id": run_id,
                    "game_id": game_id,
                    "week": week,
                    "role": role,
                    "inventory": 12,
                    "backlog": 0,
                    "order_placed": 4,
                    "shipment_received": 4,
                    "customer_demand": 4 if role == "retailer" else None,
                    "cost_week": 6.0,
                    "cost_cum": 6.0 * week,
                }
            )
    return rows
