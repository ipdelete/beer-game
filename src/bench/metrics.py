"""Registered DuckDB metrics for Beer Game bundles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import duckdb

from src.bench import reducers

MetricFn = Callable[[duckdb.DuckDBPyConnection], Any]
ReducerFn = Callable[[list[float]], float]

_METRIC_REGISTRY: dict[str, MetricFn] = {}
DEFAULT_REDUCER_SEED = 0
LOWER_IS_BETTER = "lower_is_better"
HIGHER_IS_BETTER = "higher_is_better"


@dataclass(frozen=True)
class ReducedMetric:
    """Reduced metric value with uncertainty and source epoch values."""

    value: float | None
    error: float | None
    n: int
    values: list[float]


def metric(
    name: str | None = None, *, direction: str = LOWER_IS_BETTER
) -> Callable[[MetricFn], MetricFn]:
    """Register a metric function by name."""

    if direction not in {LOWER_IS_BETTER, HIGHER_IS_BETTER}:
        raise ValueError(f"Unknown metric direction: {direction}")

    def decorator(fn: MetricFn) -> MetricFn:
        metric_name = name or fn.__name__
        _METRIC_REGISTRY[metric_name] = fn
        setattr(fn, "metric_name", metric_name)
        setattr(fn, "metric_direction", direction)
        return fn

    return decorator


def list_metrics() -> list[str]:
    """Return registered metric names in sorted order."""

    return sorted(_METRIC_REGISTRY)


def metric_direction(name: str) -> str:
    """Return whether lower or higher values are better for a metric."""

    if name not in _METRIC_REGISTRY:
        raise KeyError(f"Unknown metric: {name}")
    return getattr(_METRIC_REGISTRY[name], "metric_direction", LOWER_IS_BETTER)


def run_metrics(
    con: duckdb.DuckDBPyConnection, names: list[str] | None = None
) -> dict[str, Any]:
    """Run registered metrics against an open bundle connection."""

    metric_names = names or list_metrics()
    unknown = sorted(set(metric_names) - set(_METRIC_REGISTRY))
    if unknown:
        raise KeyError(f"Unknown metrics: {', '.join(unknown)}")
    return {name: _METRIC_REGISTRY[name](con) for name in metric_names}


def metric_epoch_values(con: duckdb.DuckDBPyConnection, name: str) -> list[Any]:
    """Run a metric once per epoch, preserving epoch order."""

    if name not in _METRIC_REGISTRY:
        raise KeyError(f"Unknown metric: {name}")
    values = []
    for epoch in _epochs(con):
        epoch_con = _epoch_connection(con, epoch)
        values.append(_METRIC_REGISTRY[name](epoch_con))
    return values


def run_metric_reducers(
    con: duckdb.DuckDBPyConnection,
    reducer_config: dict[str, tuple[ReducerFn, ReducerFn | None]] | None = None,
    *,
    seed: int = DEFAULT_REDUCER_SEED,
) -> dict[str, ReducedMetric]:
    """Reduce per-epoch metric values with configurable point/error reducers."""

    config = reducer_config or {}
    reduced = {}
    for name in list_metrics():
        point_reducer, error_reducer = config.get(
            name, (reducers.mean, reducers.bootstrap_stderr)
        )
        valid_values = [
            float(value)
            for value in metric_epoch_values(con, name)
            if isinstance(value, int | float)
        ]
        if not valid_values:
            reduced[name] = ReducedMetric(value=None, error=None, n=0, values=[])
            continue

        error = None
        if len(valid_values) > 1 and error_reducer is not None:
            error = _call_error_reducer(error_reducer, valid_values, seed)
        reduced[name] = ReducedMetric(
            value=point_reducer(valid_values),
            error=error,
            n=len(valid_values),
            values=valid_values,
        )
    return reduced


@metric()
def bullwhip_ratio(con: duckdb.DuckDBPyConnection) -> float | None:
    """Mean per-game Var(factory orders) / Var(customer demand).

    Customer demand is read from retailer `states.customer_demand` rows.
    Games with fewer than two samples, missing variance, or zero customer-demand
    variance are excluded. Returns `None` when no game has a valid ratio.
    """

    key_columns = _game_key_columns(con, "states")
    join_keys = ", ".join(key_columns)
    rows = con.execute(f"""
        WITH demand AS (
          SELECT
            {join_keys},
            var_samp(customer_demand) AS demand_var
          FROM states
          WHERE role = 'retailer' AND customer_demand IS NOT NULL
          GROUP BY {join_keys}
        ),
        factory AS (
          SELECT
            {join_keys},
            var_samp(order_placed) AS factory_var
          FROM states
          WHERE role = 'factory'
          GROUP BY {join_keys}
        )
        SELECT factory.factory_var / demand.demand_var AS ratio
        FROM factory
        JOIN demand USING ({join_keys})
        WHERE demand.demand_var IS NOT NULL
          AND demand.demand_var != 0
          AND factory.factory_var IS NOT NULL
        """).fetchall()
    ratios = [row[0] for row in rows if row[0] is not None]
    if not ratios:
        return None
    return float(sum(ratios) / len(ratios))


@metric(direction=HIGHER_IS_BETTER)
def parse_success_rate(con: duckdb.DuckDBPyConnection) -> float | None:
    """Fraction of decision rows with `parse_ok = true`.

    `NULL` parse flags count as failures. Returns `None` when there are no
    decision rows.
    """

    value = con.execute("""
        SELECT avg(CASE WHEN parse_ok THEN 1.0 ELSE 0.0 END)
        FROM decisions
        """).fetchone()[0]
    return None if value is None else float(value)


@metric()
def recovery_time(con: duckdb.DuckDBPyConnection) -> int | float | None:
    """Mean elapsed weeks from a step shock until system pressure stabilizes.

    System pressure is `sum(inventory + backlog)` across all roles for a game
    week. For step scenarios, a game recovers at the first week after
    `params.step_week` where the current 5-week rolling mean is within 20% of a
    stable final 10-week target. The final window must itself have coefficient
    of variation at most 20%. Returns `None` when no step game recovers.
    """

    recoveries = []
    for game in _step_games(con):
        series = _pressure_series(con, game)
        recovered = _game_recovery_time(series, game["step_week"])
        if recovered is not None:
            recoveries.append(recovered)

    if not recoveries:
        return None
    if len(recoveries) == 1:
        return recoveries[0]
    return float(sum(recoveries) / len(recoveries))


@metric()
def total_cost(con: duckdb.DuckDBPyConnection) -> float | None:
    """Sum of `states.cost_week` across all rows.

    Returns `None` when the bundle has no state cost rows.
    """

    value = con.execute("SELECT sum(cost_week) FROM states").fetchone()[0]
    return None if value is None else float(value)


def epoch_count(con: duckdb.DuckDBPyConnection) -> int:
    """Return the number of distinct epochs in the games view."""

    return con.execute("SELECT count(DISTINCT epoch) FROM games").fetchone()[0]


def _epochs(con: duckdb.DuckDBPyConnection) -> list[int]:
    return [
        int(row[0])
        for row in con.execute(
            "SELECT DISTINCT epoch FROM games ORDER BY epoch"
        ).fetchall()
    ]


def _epoch_connection(
    con: duckdb.DuckDBPyConnection, epoch: int
) -> duckdb.DuckDBPyConnection:
    filtered = duckdb.connect()
    has_bundle_id = "bundle_id" in _view_columns(con, "games")

    _copy_query(
        filtered, "manifest", con.execute("SELECT * FROM manifest").to_arrow_table()
    )
    _copy_query(
        filtered,
        "scenarios",
        con.execute("SELECT * FROM scenarios").to_arrow_table(),
    )
    _copy_query(
        filtered,
        "games",
        con.execute("SELECT * FROM games WHERE epoch = ?", [epoch]).to_arrow_table(),
    )
    _copy_query(
        filtered,
        "decisions",
        con.execute(
            "SELECT * FROM decisions WHERE epoch = ?", [epoch]
        ).to_arrow_table(),
    )

    if has_bundle_id:
        states_sql = """
            SELECT states.*
            FROM states
            JOIN games USING (bundle_id, game_id)
            WHERE games.epoch = ?
            """
    else:
        states_sql = """
            SELECT states.*
            FROM states
            JOIN games USING (game_id)
            WHERE games.epoch = ?
            """
    _copy_query(
        filtered,
        "states",
        con.execute(states_sql, [epoch]).to_arrow_table(),
    )
    return filtered


def _copy_query(
    con: duckdb.DuckDBPyConnection, view_name: str, arrow_table: Any
) -> None:
    source_name = f"{view_name}_source"
    con.register(source_name, arrow_table)
    con.execute(f"CREATE TABLE {view_name} AS SELECT * FROM {source_name}")
    con.unregister(source_name)


def _call_error_reducer(reducer_fn: ReducerFn, values: list[float], seed: int) -> float:
    if reducer_fn is reducers.bootstrap_stderr:
        return reducers.bootstrap_stderr(values, seed=seed)
    return reducer_fn(values)


def _game_key_columns(con: duckdb.DuckDBPyConnection, view_name: str) -> list[str]:
    columns = _view_columns(con, view_name)
    return ["bundle_id", "game_id"] if "bundle_id" in columns else ["game_id"]


def _view_columns(con: duckdb.DuckDBPyConnection, view_name: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({view_name})").fetchall()}


def _step_games(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    has_bundle_id = "bundle_id" in _view_columns(con, "games")
    bundle_select = "games.bundle_id," if has_bundle_id else ""
    rows = con.execute(f"""
        SELECT
          {bundle_select}
          games.game_id,
          games.scenario_id,
          scenarios.params
        FROM games
        JOIN scenarios
          ON games.scenario_id = scenarios.scenario_id
          {"AND games.bundle_id = scenarios.bundle_id" if has_bundle_id else ""}
        WHERE scenarios.demand_pattern = 'step'
        """).fetchall()

    games = []
    for row in rows:
        offset = 1 if has_bundle_id else 0
        params = row[offset + 2]
        step_week = _param_int(params, "step_week")
        if step_week is None:
            continue
        game: dict[str, Any] = {
            "game_id": row[offset],
            "scenario_id": row[offset + 1],
            "step_week": step_week,
        }
        if has_bundle_id:
            game["bundle_id"] = row[0]
        games.append(game)
    return games


def _pressure_series(
    con: duckdb.DuckDBPyConnection, game: dict[str, Any]
) -> list[tuple[int, float]]:
    where = ["game_id = ?"]
    params: list[Any] = [game["game_id"]]
    if "bundle_id" in game:
        where.insert(0, "bundle_id = ?")
        params.insert(0, game["bundle_id"])

    return [
        (int(row[0]), float(row[1]))
        for row in con.execute(
            f"""
            SELECT week, sum(inventory + backlog) AS pressure
            FROM states
            WHERE {" AND ".join(where)}
            GROUP BY week
            ORDER BY week
            """,
            params,
        ).fetchall()
        if row[1] is not None
    ]


def _game_recovery_time(series: list[tuple[int, float]], step_week: int) -> int | None:
    if len(series) < 10:
        return None

    values = [value for _, value in series]
    final_window = values[-10:]
    target = sum(final_window) / len(final_window)
    if target <= 0:
        return None

    variance = sum((value - target) ** 2 for value in final_window) / len(final_window)
    coefficient_of_variation = variance**0.5 / target
    if coefficient_of_variation > 0.2:
        return None

    lower = target * 0.8
    upper = target * 1.2
    for index in range(4, len(series)):
        week = series[index][0]
        if week <= step_week:
            continue
        window_mean = sum(values[index - 4 : index + 1]) / 5
        if lower <= window_mean <= upper:
            return week - step_week
    return None


def _param_int(params: Any, key: str) -> int | None:
    if isinstance(params, dict):
        value = params.get(key)
    else:
        value = None
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None
