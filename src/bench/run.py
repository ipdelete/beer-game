"""Run a single Beer Game and write a schema-conformant `.eval` bundle."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.bench.config import load_config
from src.bench.runner import ACTIVE_RELEASE, run_matrix
from src.bench.scenarios import parse_release
from src.gabm.agent import DEFAULT_ENDPOINT, DEFAULT_MODEL

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
    parser.add_argument("--epochs", type=int, default=1, help="Repeated games to run")
    parser.add_argument("--config", type=Path, default=None, help="Resolved run YAML")
    parser.add_argument(
        "--active-release", type=str, default=None, help="Scenario release pin"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable response cache"
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refresh response cache entries without reading existing entries",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=None, help="Response cache dir"
    )
    parser.add_argument("--parallel", type=int, default=None, help="Worker count")
    parser.add_argument("--force", action="store_true", help="Rerun existing bundle")
    parser.add_argument(
        "--no-retry-errors",
        action="store_true",
        help="Keep failed games when resuming instead of retrying them",
    )
    args = parser.parse_args(argv)
    if args.config is None and args.epochs < 1:
        parser.error("--epochs must be at least 1")
    if args.no_cache and args.refresh_cache:
        parser.error("--no-cache and --refresh-cache are mutually exclusive")

    bundle_path = run_bundle(
        turns=args.turns,
        mode=args.mode,
        root=args.root,
        run_id=args.run_id,
        run_seed=args.run_seed,
        epochs=args.epochs,
        config_path=args.config,
        active_release=args.active_release,
        no_cache=args.no_cache,
        refresh_cache=args.refresh_cache,
        cache_dir=args.cache_dir,
        parallel=args.parallel,
        force=args.force,
        no_retry_errors=args.no_retry_errors,
    )
    print(bundle_path)


def run_bundle(
    *,
    turns: int = 36,
    mode: str = "mechanistic",
    root: Path | str = Path("runs"),
    run_id: str | None = None,
    run_seed: int = 12345,
    epochs: int = 1,
    config_path: Path | str | None = None,
    config: dict | None = None,
    active_release: str | None = None,
    no_cache: bool = False,
    refresh_cache: bool = False,
    cache_dir: Path | str | None = None,
    parallel: int | None = None,
    force: bool = False,
    no_retry_errors: bool = False,
) -> Path:
    """Run one Beer Game and write an `.eval` bundle."""

    if config_path is not None and config is not None:
        raise ValueError("pass either config_path or config, not both")
    if no_cache and refresh_cache:
        raise ValueError("no_cache and refresh_cache are mutually exclusive")
    if config_path is not None:
        config = load_config(config_path)

    if config is None:
        if epochs < 1:
            raise ValueError("epochs must be at least 1")
        selected_active_release = active_release or ACTIVE_RELEASE
        parse_release(selected_active_release)
        scenario = _scenario(turns, selected_active_release)
        model = _model(mode)
        config = {
            "schema_version": "1.0.0",
            "active_release": selected_active_release,
            "weeks": turns,
            "epochs": epochs,
            "mode": mode,
            "run_seed": run_seed,
            "runner": {"parallel": 1, "persist_traces": False},
            "cache": {"enabled": True},
            "scenarios": [scenario],
            "models": [model],
            "telemetry": {"otlp_endpoint": None},
        }
    else:
        if active_release is not None:
            config = {**config, "active_release": active_release}

    return run_matrix(
        config,
        root=root,
        run_id=run_id,
        parallel=parallel,
        force=force,
        no_retry_errors=no_retry_errors,
        no_cache=no_cache,
        refresh_cache=refresh_cache,
        cache_dir=cache_dir,
    )


def _scenario(turns: int, release_date: str = ACTIVE_RELEASE) -> dict:
    return {
        "scenario_id": SCENARIO_ID if turns == 36 else f"step_4_8_{turns}w",
        "demand_pattern": "step",
        "params": {"low": 4, "high": 8, "step_week": 5},
        "weeks": turns,
        "costs": {"holding": HOLDING_COST, "backlog": BACKLOG_COST},
        "scenario_seed": SCENARIO_SEED,
        "release_date": release_date,
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
        "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
        "temperature": 0.4,
        "top_p": None,
    }


if __name__ == "__main__":
    main()
