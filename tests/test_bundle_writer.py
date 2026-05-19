import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.bundle import DECISIONS_SCHEMA, STATES_SCHEMA
from src.bench.run import run_bundle


def test_run_bundle_writes_required_files(tmp_path):
    bundle_path = run_bundle(turns=1, root=tmp_path, run_id="test-run")

    assert bundle_path == tmp_path / "test-run.eval"
    assert (bundle_path / "manifest.json").exists()
    assert (bundle_path / "scenarios.jsonl").exists()
    assert (bundle_path / "games.jsonl").exists()
    assert (bundle_path / "decisions.parquet").exists()
    assert (bundle_path / "states.parquet").exists()


def test_run_bundle_manifest_and_game_metadata(tmp_path):
    bundle_path = run_bundle(turns=1, root=tmp_path, run_id="test-run")

    manifest = json.loads((bundle_path / "manifest.json").read_text())
    game = json.loads((bundle_path / "games.jsonl").read_text())

    assert manifest["schema_version"] == "1.0.0"
    assert manifest["run_id"] == "test-run"
    assert manifest["ended_at"] is not None
    assert manifest["models"][0]["id"] == "mechanistic"
    assert manifest["scenario_ids"] == ["step_4_8_1w"]
    assert game["status"] == "ok"
    assert game["ended_at"] is not None
    assert game["total_cost"] == 24.0
    assert game["demand_hash"]


def test_run_bundle_writes_expected_parquet_schemas_and_rows(tmp_path):
    bundle_path = run_bundle(turns=2, root=tmp_path, run_id="test-run")

    decisions = pq.read_table(bundle_path / "decisions.parquet")
    states = pq.read_table(bundle_path / "states.parquet")

    assert decisions.schema.equals(DECISIONS_SCHEMA)
    assert states.schema.equals(STATES_SCHEMA)
    assert decisions.num_rows == 8
    assert states.num_rows == 8


def test_state_customer_demand_only_on_retailer_rows(tmp_path):
    bundle_path = run_bundle(turns=1, root=tmp_path, run_id="test-run")
    states = pq.read_table(bundle_path / "states.parquet").to_pylist()

    retailer = [row for row in states if row["role"] == "retailer"]
    non_retailers = [row for row in states if row["role"] != "retailer"]

    assert [row["customer_demand"] for row in retailer] == [4]
    assert all(row["customer_demand"] is None for row in non_retailers)


def test_decision_token_fields_are_nullable_placeholders(tmp_path):
    bundle_path = run_bundle(turns=1, root=tmp_path, run_id="test-run")
    decisions = pq.read_table(bundle_path / "decisions.parquet").to_pylist()

    assert len(decisions) == 4
    assert {row["role"] for row in decisions} == {
        "retailer",
        "wholesaler",
        "distributor",
        "factory",
    }
    assert all(row["input_tokens"] is None for row in decisions)
    assert all(row["output_tokens"] is None for row in decisions)
    assert all(row["latency_ms"] is None for row in decisions)
    assert all(row["parse_strategy"] == "mechanistic" for row in decisions)
