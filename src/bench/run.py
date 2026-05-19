"""Run a single Beer Game and write a schema-conformant `.eval` bundle."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Callable

from src.bench.bundle import (
    ROLE_NAMES,
    ROLE_TITLES,
    BundleWriter,
    demand_hash,
    make_sortable_id,
    stable_hash_int,
    utc_now,
)
from src.engine.simulation import BeerGameEngine
from src.engine.state import PlayerView
from src.gabm.agent import DEFAULT_ENDPOINT, DEFAULT_MODEL
from src.gabm.agent import gabm_decision, reset_state as reset_gabm
from src.mechanistic.agent import mechanistic_decision, reset_state as reset_mech

SCENARIO_ID = "step_4_8_36w"
ACTIVE_RELEASE = "2026-Q2"
SCENARIO_SEED = 42
HOLDING_COST = 0.5
BACKLOG_COST = 1.0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write one Beer Game .eval bundle")
    parser.add_argument("--turns", type=int, default=36, help="Weeks to simulate")
    parser.add_argument(
        "--mode",
        choices=["mechanistic", "gabm"],
        default="mechanistic",
        help="Decision strategy to run",
    )
    parser.add_argument("--root", type=Path, default=Path("runs"), help="Output root")
    parser.add_argument("--run-id", type=str, default=None, help="Optional run id")
    parser.add_argument("--run-seed", type=int, default=12345, help="Top-level seed")
    args = parser.parse_args(argv)

    bundle_path = run_bundle(
        turns=args.turns,
        mode=args.mode,
        root=args.root,
        run_id=args.run_id,
        run_seed=args.run_seed,
    )
    print(bundle_path)


def run_bundle(
    *,
    turns: int = 36,
    mode: str = "mechanistic",
    root: Path | str = Path("runs"),
    run_id: str | None = None,
    run_seed: int = 12345,
) -> Path:
    """Run one Beer Game and write an `.eval` bundle."""

    scenario = _scenario(turns)
    model = _model(mode)
    config = {
        "active_release": ACTIVE_RELEASE,
        "weeks": turns,
        "epochs": 1,
        "mode": mode,
        "run_seed": run_seed,
        "scenarios": [scenario],
        "models": [model],
    }
    writer = BundleWriter(root, run_id=run_id)
    writer.start(models=[model], scenarios=[scenario], config=config)

    game_id = make_sortable_id("game")
    demand_seed = stable_hash_int((run_seed, scenario["scenario_id"], SCENARIO_SEED, 0))
    llm_seed = stable_hash_int((run_seed, scenario["scenario_id"], model["id"], 0))

    decision_rows: list[dict] = []

    def record_decision(view: PlayerView, decision: int) -> None:
        decision_rows.append(
            {
                "run_id": writer.run_id,
                "game_id": game_id,
                "scenario_id": scenario["scenario_id"],
                "epoch": 0,
                "week": view.week,
                "role": _role_name(view.role),
                "model_request": model["id"],
                "model_response": None if mode == "mechanistic" else model["id"],
                "provider": model["provider"],
                "temperature": model.get("temperature"),
                "top_p": model.get("top_p"),
                "seed_request": llm_seed,
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "cache_read_input_tokens": None,
                "finish_reason": None,
                "response_id": None,
                "latency_ms": None,
                "time_to_first_chunk_ms": None,
                "parse_ok": True,
                "parse_strategy": mode,
                "decision_int": decision,
                "context_used": None,
                "context_window": None,
                "cache_hit": False,
                "error_type": None,
                "raw_response_ref": None,
            }
        )

    decision_fn = _decision_fn(mode, record_decision)
    engine = BeerGameEngine(decision_fn=decision_fn)

    started = time.monotonic()
    status = "ok"
    error = None
    try:
        for _ in range(turns):
            engine.simulate_week()
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        wall_seconds = time.monotonic() - started

    ended_at = utc_now()
    writer.append_decisions(decision_rows)
    writer.append_states(_state_rows(writer.run_id, game_id, engine))
    writer.append_game(
        {
            "game_id": game_id,
            "run_id": writer.run_id,
            "scenario_id": scenario["scenario_id"],
            "model": model["id"],
            "epoch": 0,
            "demand_seed": demand_seed,
            "llm_seed": llm_seed,
            "started_at": writer.started_at,
            "ended_at": ended_at,
            "status": status,
            "error": error,
            "demand_hash": demand_hash(engine.order_history["Customer"]),
            "total_cost": (
                sum(engine.get_total_costs().values()) if status == "ok" else None
            ),
            "wall_seconds": wall_seconds,
        }
    )
    return writer.finish()


def _decision_fn(
    mode: str, record_decision: Callable[[PlayerView, int], None]
) -> Callable[[PlayerView], int]:
    if mode == "mechanistic":
        reset_mech()
        base_decision = mechanistic_decision
    else:
        reset_gabm()
        base_decision = gabm_decision

    def decide(view: PlayerView) -> int:
        decision = max(0, int(base_decision(view)))
        record_decision(view, decision)
        return decision

    return decide


def _scenario(turns: int) -> dict:
    return {
        "scenario_id": SCENARIO_ID if turns == 36 else f"step_4_8_{turns}w",
        "demand_pattern": "step",
        "params": {"low": 4, "high": 8, "step_week": 5},
        "weeks": turns,
        "costs": {"holding": HOLDING_COST, "backlog": BACKLOG_COST},
        "scenario_seed": SCENARIO_SEED,
        "release_date": ACTIVE_RELEASE,
        "removal_date": None,
    }


def _model(mode: str) -> dict:
    if mode == "mechanistic":
        return {
            "id": "mechanistic",
            "provider": "mechanistic",
            "endpoint": None,
            "temperature": None,
            "top_p": None,
        }
    return {
        "id": os.getenv("LLM_MODEL", DEFAULT_MODEL),
        "provider": "openai-compatible",
        "endpoint": os.getenv("LLM_ENDPOINT", DEFAULT_ENDPOINT),
        "temperature": 0.4,
        "top_p": None,
    }


def _state_rows(run_id: str, game_id: str, engine: BeerGameEngine) -> list[dict]:
    rows = []
    cumulative_cost = {role_title: 0.0 for role_title in ROLE_TITLES}
    turns = engine.current_week
    for week_index in range(turns):
        for role_title, role_name in zip(ROLE_TITLES, ROLE_NAMES):
            record = engine.history[role_title][week_index]
            cumulative_cost[role_title] += record.cost
            rows.append(
                {
                    "run_id": run_id,
                    "game_id": game_id,
                    "week": record.week,
                    "role": role_name,
                    "inventory": record.inventory,
                    "backlog": record.backlog,
                    "order_placed": record.order_placed,
                    "shipment_received": record.shipment_received,
                    "customer_demand": (
                        engine.order_history["Customer"][week_index]
                        if role_name == "retailer"
                        else None
                    ),
                    "cost_week": record.cost,
                    "cost_cum": cumulative_cost[role_title],
                }
            )
    return rows


def _role_name(role_title: str) -> str:
    role = role_title.lower()
    if role not in ROLE_NAMES:
        raise ValueError(f"Unknown Beer Game role: {role_title}")
    return role


if __name__ == "__main__":
    main()
