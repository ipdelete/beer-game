"""Paired-bootstrap model comparison helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import duckdb
import numpy as np

from src.bench.metrics import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    list_metrics,
    metric_direction,
    run_metrics,
)


@dataclass(frozen=True)
class ComparisonResult:
    metric: str
    baseline: str
    challenger: str
    direction: str
    baseline_mean: float
    challenger_mean: float
    diff: float
    ci_low: float
    ci_high: float
    p_value: float
    n_pairs: int
    significant: bool
    better: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def paired_bootstrap(
    baseline: list[float],
    challenger: list[float],
    *,
    metric_name: str,
    baseline_name: str,
    challenger_name: str,
    num_samples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 12345,
    direction: str = LOWER_IS_BETTER,
) -> ComparisonResult:
    """Compare paired metric samples with a deterministic bootstrap."""

    if len(baseline) != len(challenger):
        raise ValueError("paired bootstrap requires equal-length samples")
    if not baseline:
        raise ValueError("paired bootstrap requires at least one pair")
    if num_samples < 1:
        raise ValueError("num_samples must be at least 1")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")

    baseline_values = np.asarray(baseline, dtype=float)
    challenger_values = np.asarray(challenger, dtype=float)
    diffs = challenger_values - baseline_values
    rng = np.random.default_rng(seed)
    sample_indices = rng.integers(0, len(diffs), size=(num_samples, len(diffs)))
    means = diffs[sample_indices].mean(axis=1)
    ci_low, ci_high = np.quantile(means, [alpha / 2, 1 - (alpha / 2)])
    p_value = 2 * min(float((means <= 0).mean()), float((means >= 0).mean()))
    p_value = min(1.0, max(1 / num_samples, p_value))
    diff = float(diffs.mean())
    significant = p_value < alpha and (float(ci_high) < 0 or float(ci_low) > 0)
    return ComparisonResult(
        metric=metric_name,
        baseline=baseline_name,
        challenger=challenger_name,
        direction=direction,
        baseline_mean=float(baseline_values.mean()),
        challenger_mean=float(challenger_values.mean()),
        diff=diff,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        p_value=p_value,
        n_pairs=len(diffs),
        significant=significant,
        better=_better_model(
            diff, significant, direction, baseline_name, challenger_name
        ),
    )


def compare_bundle(
    con: duckdb.DuckDBPyConnection,
    *,
    baseline: str,
    challenger: str,
    metric_names: list[str] | None = None,
    num_samples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 12345,
) -> tuple[list[ComparisonResult], list[str]]:
    """Compare two models across all paired scenario/epoch cells."""

    _ensure_models(con, baseline, challenger)
    warnings: list[str] = []
    results: list[ComparisonResult] = []
    for metric_name in metric_names or list_metrics():
        baseline_values, challenger_values, metric_warnings = paired_metric_values(
            con, metric_name, baseline=baseline, challenger=challenger
        )
        warnings.extend(metric_warnings)
        if not baseline_values:
            warnings.append(f"{metric_name}: skipped because no numeric pairs matched")
            continue
        if len(baseline_values) < 3:
            warnings.append(
                f"{metric_name}: only {len(baseline_values)} pairs; interpret CI cautiously"
            )
        results.append(
            paired_bootstrap(
                baseline_values,
                challenger_values,
                metric_name=metric_name,
                baseline_name=baseline,
                challenger_name=challenger,
                num_samples=num_samples,
                alpha=alpha,
                seed=seed,
                direction=metric_direction(metric_name),
            )
        )
    return results, warnings


def paired_metric_values(
    con: duckdb.DuckDBPyConnection,
    metric_name: str,
    *,
    baseline: str,
    challenger: str,
) -> tuple[list[float], list[float], list[str]]:
    """Return metric values paired by scenario and epoch."""

    warnings = []
    baseline_games = _games_by_pair(con, baseline)
    challenger_games = _games_by_pair(con, challenger)
    missing = sorted(set(baseline_games) ^ set(challenger_games))
    if missing:
        warnings.append(f"{metric_name}: dropped {len(missing)} unpaired cells")

    baseline_values = []
    challenger_values = []
    for key in sorted(set(baseline_games) & set(challenger_games)):
        baseline_game = baseline_games[key]
        challenger_game = challenger_games[key]
        if baseline_game["demand_seed"] != challenger_game["demand_seed"]:
            warnings.append(
                f"{metric_name}: dropped {key[0]} epoch {key[1]} "
                "because demand_seed differed"
            )
            continue
        baseline_value = _metric_for_cell(con, metric_name, baseline_game)
        challenger_value = _metric_for_cell(con, metric_name, challenger_game)
        if not isinstance(baseline_value, int | float) or not isinstance(
            challenger_value, int | float
        ):
            warnings.append(
                f"{metric_name}: dropped {key[0]} epoch {key[1]} "
                "because one side had no numeric value"
            )
            continue
        baseline_values.append(float(baseline_value))
        challenger_values.append(float(challenger_value))
    return baseline_values, challenger_values, warnings


def _ensure_models(
    con: duckdb.DuckDBPyConnection, baseline: str, challenger: str
) -> None:
    models = [
        row[0]
        for row in con.execute(
            "SELECT DISTINCT model FROM games ORDER BY model"
        ).fetchall()
    ]
    missing = [model for model in (baseline, challenger) if model not in models]
    if missing:
        raise ValueError(
            f"Model not found: {', '.join(missing)}. Available models: {', '.join(models)}"
        )


def _games_by_pair(
    con: duckdb.DuckDBPyConnection, model: str
) -> dict[tuple[str, int], dict]:
    return {
        (row[0], int(row[1])): {
            "scenario_id": row[0],
            "epoch": int(row[1]),
            "model": row[2],
            "game_id": row[3],
            "demand_seed": row[4],
        }
        for row in con.execute(
            """
            SELECT scenario_id, epoch, model, game_id, demand_seed
            FROM games
            WHERE model = ? AND status = 'ok'
            ORDER BY scenario_id, epoch
            """,
            [model],
        ).fetchall()
    }


def _metric_for_cell(
    con: duckdb.DuckDBPyConnection, metric_name: str, game: dict
) -> Any:
    cell = duckdb.connect()
    _copy_view(cell, "manifest", con.execute("SELECT * FROM manifest").to_arrow_table())
    _copy_view(
        cell,
        "scenarios",
        con.execute(
            "SELECT * FROM scenarios WHERE scenario_id = ?", [game["scenario_id"]]
        ).to_arrow_table(),
    )
    _copy_view(
        cell,
        "games",
        con.execute(
            "SELECT * FROM games WHERE game_id = ?", [game["game_id"]]
        ).to_arrow_table(),
    )
    _copy_view(
        cell,
        "decisions",
        con.execute(
            "SELECT * FROM decisions WHERE game_id = ?", [game["game_id"]]
        ).to_arrow_table(),
    )
    _copy_view(
        cell,
        "states",
        con.execute(
            "SELECT * FROM states WHERE game_id = ?", [game["game_id"]]
        ).to_arrow_table(),
    )
    return run_metrics(cell, [metric_name])[metric_name]


def _copy_view(target: duckdb.DuckDBPyConnection, name: str, table: Any) -> None:
    target.register(f"_{name}_arrow", table)
    target.execute(f"CREATE VIEW {name} AS SELECT * FROM _{name}_arrow")


def _better_model(
    diff: float, significant: bool, direction: str, baseline: str, challenger: str
) -> str:
    if not significant:
        return "none"
    if direction == LOWER_IS_BETTER:
        return challenger if diff < 0 else baseline
    if direction == HIGHER_IS_BETTER:
        return challenger if diff > 0 else baseline
    raise ValueError(f"Unknown metric direction: {direction}")
