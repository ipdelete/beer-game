import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import pytest
import duckdb

from bench.metrics import total_cost as compat_total_cost
from src.bench.bundle import BundleWriter, ROLE_NAMES
from src.bench.metrics import (
    bullwhip_ratio,
    list_metrics,
    metric_epoch_values,
    parse_success_rate,
    run_metric_reducers,
    recovery_time,
    run_metrics,
    total_cost,
)
from src.bench.query import open_bundle


def test_metric_registry_lists_sorted_metrics_and_runs_selected(tmp_path):
    bundle_path = _write_metric_bundle(tmp_path, "stable")
    con = open_bundle(bundle_path)

    assert list_metrics() == [
        "bullwhip_ratio",
        "parse_success_rate",
        "recovery_time",
        "total_cost",
    ]
    assert run_metrics(con, ["total_cost"]) == {"total_cost": total_cost(con)}
    with pytest.raises(KeyError, match="Unknown metrics: nope"):
        run_metrics(con, ["nope"])


def test_metrics_are_importable_from_compat_package():
    assert compat_total_cost is total_cost


def test_bullwhip_ratio_is_one_for_matching_order_variance(tmp_path):
    bundle_path = _write_metric_bundle(tmp_path, "stable")
    con = open_bundle(bundle_path)

    assert bullwhip_ratio(con) == pytest.approx(1.0)


def test_bullwhip_ratio_is_greater_than_one_for_amplified_orders(tmp_path):
    bundle_path = _write_metric_bundle(
        tmp_path,
        "oscillating",
        factory_orders=[4, 4, 16, 0, 16, 0, 16, 0, 16, 0, 16, 0],
    )
    con = open_bundle(bundle_path)

    assert bullwhip_ratio(con) > 1.0


def test_parse_success_rate_counts_null_as_failure(tmp_path):
    bundle_path = _write_metric_bundle(tmp_path, "parse")
    con = open_bundle(bundle_path)

    assert parse_success_rate(con) == pytest.approx(1 / 3)


def test_recovery_time_returns_none_when_system_never_stabilizes(tmp_path):
    bundle_path = _write_metric_bundle(
        tmp_path,
        "never-recovers",
        pressure=[20, 20, 80, 20, 90, 20, 100, 20, 110, 20, 120, 20],
    )
    con = open_bundle(bundle_path)

    assert recovery_time(con) is None


def test_total_cost_sums_state_cost_rows(tmp_path):
    bundle_path = _write_metric_bundle(tmp_path, "cost")
    con = open_bundle(bundle_path)

    assert total_cost(con) == pytest.approx(48.0)


def test_metric_reducers_run_against_each_epoch(tmp_path):
    first_bundle = _write_metric_bundle(tmp_path, "epoch-zero")
    second_bundle = _write_metric_bundle(
        tmp_path / "second",
        "epoch-one",
        factory_orders=[4, 4, 16, 0, 16, 0, 16, 0, 16, 0, 16, 0],
    )

    con = _merged_epoch_connection(first_bundle, second_bundle)

    assert metric_epoch_values(con, "total_cost") == [48.0, 48.0]
    reduced = run_metric_reducers(con)
    assert reduced["total_cost"].value == pytest.approx(48.0)
    assert reduced["total_cost"].error == pytest.approx(0.0)
    assert reduced["total_cost"].n == 2
    assert reduced["bullwhip_ratio"].values[0] == pytest.approx(1.0)
    assert reduced["bullwhip_ratio"].values[1] > 1.0


def _write_metric_bundle(
    tmp_path: Path,
    run_id: str,
    *,
    factory_orders: list[int] | None = None,
    pressure: list[int] | None = None,
) -> Path:
    customer_demand = [4, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8]
    factory_orders = factory_orders or customer_demand
    pressure = pressure or [80, 70, 60, 50, 40, 30, 20, 20, 20, 20, 20, 20]
    weeks = len(customer_demand)
    scenario = {
        "scenario_id": "step_fixture",
        "demand_pattern": "step",
        "params": {"low": 4, "high": 8, "step_week": 2},
        "weeks": weeks,
        "costs": {"holding": 0.5, "backlog": 1.0},
        "scenario_seed": 42,
        "release_date": "2026-Q2",
        "removal_date": None,
    }
    model = {
        "id": "metric-model",
        "provider": "test",
        "endpoint": None,
        "temperature": None,
        "top_p": None,
    }
    game_id = f"{run_id}-game"
    writer = BundleWriter(tmp_path, run_id=run_id)
    writer.start(
        models=[model],
        scenarios=[scenario],
        config={
            "active_release": "2026-Q2",
            "run_seed": 123,
            "weeks": weeks,
            "epochs": 1,
        },
    )
    writer.append_game(
        {
            "game_id": game_id,
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
            "total_cost": 48.0,
            "wall_seconds": 0.0,
        }
    )
    writer.append_decisions(_decision_rows(run_id, game_id))
    writer.append_states(
        _state_rows(run_id, game_id, customer_demand, factory_orders, pressure)
    )
    return writer.finish()


def _merged_epoch_connection(first_bundle: Path, second_bundle: Path):
    first = open_bundle(first_bundle)
    second = open_bundle(second_bundle)
    con = duckdb.connect()
    for view_name in ("manifest", "scenarios", "games", "decisions", "states"):
        first_table = first.execute(f"SELECT * FROM {view_name}").to_arrow_table()
        second_table = second.execute(
            f"""
            SELECT * REPLACE (1 AS epoch)
            FROM {view_name}
            """
            if view_name in {"games", "decisions"}
            else f"SELECT * FROM {view_name}"
        ).to_arrow_table()
        con.register("first_table", first_table)
        con.register("second_table", second_table)
        con.execute(f"""
            CREATE TABLE {view_name} AS
            SELECT * FROM first_table
            UNION ALL BY NAME
            SELECT * FROM second_table
            """)
        con.unregister("first_table")
        con.unregister("second_table")
    return con


def _decision_rows(run_id: str, game_id: str) -> list[dict]:
    rows = []
    parse_values = [True, False, None]
    for index, parse_ok in enumerate(parse_values, start=1):
        rows.append(
            {
                "run_id": run_id,
                "game_id": game_id,
                "scenario_id": "step_fixture",
                "epoch": 0,
                "week": index,
                "role": "retailer",
                "model_request": "metric-model",
                "model_response": "metric-model",
                "provider": "test",
                "temperature": None,
                "top_p": None,
                "seed_request": 2,
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "cache_read_input_tokens": None,
                "finish_reason": "stop",
                "response_id": f"resp-{index}",
                "latency_ms": None,
                "time_to_first_chunk_ms": None,
                "parse_ok": parse_ok,
                "parse_strategy": "fixture",
                "decision_int": 4,
                "context_used": None,
                "context_window": None,
                "cache_hit": False,
                "error_type": None,
                "raw_response_ref": None,
            }
        )
    return rows


def _state_rows(
    run_id: str,
    game_id: str,
    customer_demand: list[int],
    factory_orders: list[int],
    pressure: list[int],
) -> list[dict]:
    rows = []
    for week_index, demand in enumerate(customer_demand):
        week = week_index + 1
        for role_index, role in enumerate(ROLE_NAMES):
            rows.append(
                {
                    "run_id": run_id,
                    "game_id": game_id,
                    "week": week,
                    "role": role,
                    "inventory": pressure[week_index] if role_index == 0 else 0,
                    "backlog": 0,
                    "order_placed": (
                        factory_orders[week_index] if role == "factory" else demand
                    ),
                    "shipment_received": 4,
                    "customer_demand": demand if role == "retailer" else None,
                    "cost_week": 1.0,
                    "cost_cum": float(week),
                }
            )
    return rows
