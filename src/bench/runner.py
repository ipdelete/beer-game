"""Matrix runner for Beer Game benchmark bundles."""

from __future__ import annotations

import contextvars
import hashlib
import itertools
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
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
from src.bench.cache import ResponseCache
from src.bench.scenarios import filter_scenarios
from src.bench.telemetry import configure_telemetry, decision_context
from src.engine.simulation import BeerGameEngine
from src.engine.state import PlayerView
from src.gabm.agent import GABMAgent, PROMPT_VERSION
from src.mechanistic.agent import ALPHA_D, BETA, S_INV

ACTIVE_RELEASE = "2026-Q2"


@dataclass(frozen=True)
class GameTask:
    scenario: dict
    model: dict
    epoch: int

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.scenario["scenario_id"], self.model["id"], self.epoch)


def run_matrix(
    config: dict,
    *,
    root: Path | str = Path("runs"),
    run_id: str | None = None,
    parallel: int | None = None,
    force: bool = False,
    no_retry_errors: bool = False,
    no_cache: bool = False,
    refresh_cache: bool = False,
    cache_dir: Path | str | None = None,
) -> Path:
    """Execute all configured scenario/model/epoch games into one bundle."""

    if no_cache and refresh_cache:
        raise ValueError("no_cache and refresh_cache are mutually exclusive")
    config = _prepare_config(config, no_cache=no_cache)
    _validate_unique(config["scenarios"], "scenario_id", "scenarios")
    _validate_unique(config["models"], "id", "models")
    worker_count = parallel if parallel is not None else config["runner"]["parallel"]
    if worker_count < 1:
        raise ValueError("parallel must be at least 1")

    root = Path(root)
    run_id = run_id or make_sortable_id("run")
    bundle_path = root / f"{run_id}.eval"
    matrix_hash = matrix_identity_hash(config)
    kept_games: list[dict] = []
    skipped: set[tuple[str, str, int]] = set()
    resume = bundle_path.exists()
    if force and resume:
        shutil.rmtree(bundle_path)
        resume = False
    if resume:
        manifest = _read_json(bundle_path / "manifest.json")
        previous_hash = manifest.get("matrix_hash") or manifest.get("config_hash")
        if previous_hash != matrix_hash:
            raise ValueError(
                "existing bundle has a different matrix identity; use --force to rerun"
            )
        kept_games, skipped = _resume_games(
            _read_jsonl(bundle_path / "games.jsonl"), no_retry_errors=no_retry_errors
        )

    writer = BundleWriter(root, run_id=run_id)
    writer.start(
        models=config["models"],
        scenarios=config["scenarios"],
        config=config,
        matrix_hash=matrix_hash,
        resume=resume,
        existing_games=kept_games,
    )

    tasks = [task for task in _tasks(config) if not _task_done(task.key, skipped)]
    has_gabm = _has_gabm(config)
    cache = (
        ResponseCache(
            cache_dir,
            enabled=config.get("cache", {}).get("enabled", True),
            refresh=refresh_cache,
        )
        if has_gabm
        else None
    )
    telemetry_session = configure_telemetry(writer) if has_gabm else None
    try:
        _run_tasks(
            tasks,
            writer=writer,
            config=config,
            cache=cache,
            parallel=worker_count,
        )
        if telemetry_session is not None:
            telemetry_session.shutdown()
            telemetry_session = None
        return writer.finish()
    finally:
        if telemetry_session is not None:
            telemetry_session.shutdown()


def matrix_identity_hash(config: dict) -> str:
    """Hash the matrix identity, excluding volatile execution controls."""

    payload = {
        "schema_version": config.get("schema_version"),
        "active_release": config.get("active_release"),
        "run_seed": config.get("run_seed"),
        "weeks": config.get("weeks"),
        "epochs": config.get("epochs"),
        "prompt_version": config.get("prompt_version"),
        "scenarios": config.get("scenarios", []),
        "models": config.get("models", []),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _prepare_config(config: dict, *, no_cache: bool) -> dict:
    selected_active_release, scenarios = filter_scenarios(
        config["scenarios"], config.get("active_release")
    )
    prepared = {
        **config,
        "active_release": selected_active_release,
        "scenarios": scenarios,
    }
    if _has_gabm(prepared) and "prompt_version" not in prepared:
        prepared = {**prepared, "prompt_version": PROMPT_VERSION}
    if no_cache:
        prepared = {
            **prepared,
            "cache": {**prepared.get("cache", {}), "enabled": False},
        }
    return prepared


def _tasks(config: dict) -> list[GameTask]:
    return [
        GameTask(scenario, model, epoch)
        for scenario, model, epoch in itertools.product(
            config["scenarios"], config["models"], range(int(config["epochs"]))
        )
    ]


def _run_tasks(
    tasks: list[GameTask],
    *,
    writer: BundleWriter,
    config: dict,
    cache: ResponseCache | None,
    parallel: int,
) -> None:
    total = len(tasks)
    if total == 0:
        return
    completed = 0

    def run_one(task: GameTask) -> None:
        _run_game(
            writer=writer,
            scenario=task.scenario,
            model=task.model,
            turns=int(task.scenario.get("weeks") or config["weeks"]),
            run_seed=int(config["run_seed"]),
            epoch=task.epoch,
            prompt_version=config.get("prompt_version"),
            cache=cache,
        )

    if parallel == 1:
        for task in tasks:
            run_one(task)
            completed += 1
            _print_progress(completed, total)
        return

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = []
        for task in tasks:
            ctx = contextvars.copy_context()
            futures.append(executor.submit(ctx.run, run_one, task))
        for future in as_completed(futures):
            future.result()
            completed += 1
            _print_progress(completed, total)


def _run_game(
    *,
    writer: BundleWriter,
    scenario: dict,
    model: dict,
    turns: int,
    run_seed: int,
    epoch: int,
    prompt_version: str | None,
    cache: ResponseCache | None,
) -> None:
    game_id = make_sortable_id("game")
    mode = _mode_for_model(model)
    demand_seed = stable_hash_int(
        (run_seed, scenario["scenario_id"], scenario["scenario_seed"], epoch)
    )
    llm_seed = stable_hash_int((run_seed, scenario["scenario_id"], model["id"], epoch))
    decision_rows: list[dict] = []

    def record_decision(view: PlayerView, decision: int) -> None:
        decision_rows.append(
            {
                "run_id": writer.run_id,
                "game_id": game_id,
                "scenario_id": scenario["scenario_id"],
                "epoch": epoch,
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

    decision_fn = _decision_fn(
        mode,
        model,
        cache,
        record_decision,
        {
            "run_id": writer.run_id,
            "game_id": game_id,
            "scenario_id": scenario["scenario_id"],
            "scenario_release": scenario.get("release_date") or ACTIVE_RELEASE,
            "epoch": epoch,
            "llm_seed": llm_seed,
            "scenario_params_hash": _scenario_params_hash(scenario),
            "demand_hash": _scenario_demand_hash(scenario, turns),
            "prompt_version": prompt_version,
        },
    )
    engine = BeerGameEngine(decision_fn=decision_fn)
    started = time.monotonic()
    status = "ok"
    error = None
    caught: Exception | None = None
    try:
        for _ in range(turns):
            engine.simulate_week()
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
        caught = exc
    wall_seconds = time.monotonic() - started
    ended_at = utc_now()

    if mode != "gabm":
        writer.append_decisions(decision_rows)
    writer.append_states(_state_rows(writer.run_id, game_id, engine))
    writer.flush_game(game_id)
    writer.append_game(
        {
            "game_id": game_id,
            "run_id": writer.run_id,
            "scenario_id": scenario["scenario_id"],
            "model": model["id"],
            "epoch": epoch,
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
    if caught is not None:
        raise caught


def _decision_fn(
    mode: str,
    model: dict,
    cache: ResponseCache | None,
    record_decision: Callable[[PlayerView, int], None],
    telemetry_fields: dict,
) -> Callable[[PlayerView], int]:
    if mode == "mechanistic":
        role_state: dict[str, float] = {}

        def decide(view: PlayerView) -> int:
            expected_demand = role_state.get(view.role, 4.0)
            expected_demand = (ALPHA_D * view.incoming_order) + (
                (1 - ALPHA_D) * expected_demand
            )
            role_state[view.role] = expected_demand
            lead_time = 2 if view.role == "Factory" else 4
            desired_ip = S_INV + lead_time * expected_demand
            inventory_gap = desired_ip - view.inventory + view.backlog - view.on_order
            decision = max(0, int(round(expected_demand + (BETA * inventory_gap))))
            record_decision(view, decision)
            return decision

        return decide

    agents: dict[str, GABMAgent] = {}

    def decide(view: PlayerView) -> int:
        with decision_context(
            **telemetry_fields,
            week=view.week,
            role=_role_name(view.role),
            cache_hit=False,
            context_used=None,
            context_window=None,
        ):
            if view.role not in agents:
                agents[view.role] = GABMAgent(view.role, config=model, cache=cache)
            return max(0, int(agents[view.role].decide(view)))

    return decide


def _resume_games(
    games: list[dict], *, no_retry_errors: bool
) -> tuple[list[dict], set[tuple[str, str, int]]]:
    kept_by_key: dict[tuple[str, str, int], dict] = {}
    for game in games:
        key = _game_key(game)
        if game.get("status") == "ok" or no_retry_errors:
            kept_by_key[key] = game
    return list(kept_by_key.values()), set(kept_by_key)


def _task_done(key: tuple[str, str, int], skipped: set[tuple[str, str, int]]) -> bool:
    return key in skipped


def _game_key(game: dict) -> tuple[str, str, int]:
    return (game["scenario_id"], game["model"], int(game["epoch"]))


def _validate_unique(items: list[dict], key: str, label: str) -> None:
    values = [item[key] for item in items]
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {label} {key}: {', '.join(duplicates)}")


def _has_gabm(config: dict) -> bool:
    return any(_mode_for_model(model) == "gabm" for model in config.get("models", []))


def _mode_for_model(model: dict) -> str:
    return "mechanistic" if model.get("provider") == "mechanistic" else "gabm"


def _scenario_params_hash(scenario: dict) -> str:
    payload = json.dumps(
        scenario.get("params", {}),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


def _scenario_demand_hash(scenario: dict, turns: int) -> str:
    pattern = scenario.get("demand_pattern")
    params = scenario.get("params", {})
    if pattern == "step":
        low = int(params.get("low", 4))
        high = int(params.get("high", 8))
        step_week = int(params.get("step_week", 5))
        demand = [low if week < step_week else high for week in range(1, turns + 1)]
        return demand_hash(demand)
    if pattern == "constant":
        demand = [int(params["value"])] * turns
        return demand_hash(demand)
    payload = json.dumps(
        {"pattern": pattern, "params": params, "turns": turns},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


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


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _print_progress(done: int, total: int) -> None:
    if total <= 1 or not sys.stderr.isatty():
        return
    width = 20
    filled = round((done / total) * width)
    bar = "#" * filled + "-" * (width - filled)
    end = "\n" if done == total else "\r"
    print(f"[{bar}] {done}/{total}", end=end, file=sys.stderr, flush=True)
