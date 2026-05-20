"""Top-level Beer Game benchmark CLI."""

from __future__ import annotations

import csv
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import click

from bench.cli._common import (
    iter_bundles,
    load_manifest,
    resolve_bundle,
    runs_dir,
    unsupported,
)
from src.bench import report as text_report
from src.bench.metrics import epoch_count, run_metric_reducers, run_metrics
from src.bench.query import open_bundle
from src.bench.run import run_bundle


def _version() -> str:
    try:
        return version("beer-game")
    except PackageNotFoundError:
        return "0.1.0"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=_version(), prog_name="bench")
def bench() -> None:
    """Beer Game benchmark CLI (#9)."""


@bench.command(help="Run a benchmark bundle (#9).")
@click.option(
    "--mode", type=click.Choice(["mechanistic", "gabm"]), default="mechanistic"
)
@click.option("--turns", type=int, default=36, show_default=True)
@click.option("--epochs", type=int, default=1, show_default=True)
@click.option("--seed", type=int, default=12345, show_default=True)
@click.option("--runs-dir", type=click.Path(path_type=Path), default=None)
@click.option("--run-id", type=str, default=None)
@click.option("--config", type=click.Path(path_type=Path), default=None)
@click.option("--active-release", type=str, default=None)
@click.option("--scenario", type=str, default=None)
@click.option("--model", type=str, default=None)
@click.option("--no-cache", is_flag=True, default=False)
@click.option("--refresh-cache", is_flag=True, default=False)
@click.option("--cache-dir", type=click.Path(path_type=Path), default=None)
@click.option("--parallel", type=int, default=None)
@click.option("--force", is_flag=True, default=False)
@click.option("--no-retry-errors", is_flag=True, default=False)
@click.option("--persist-traces", is_flag=True, default=False)
def run(
    mode: str,
    turns: int,
    epochs: int,
    seed: int,
    runs_dir: Path | None,
    run_id: str | None,
    config: Path | None,
    active_release: str | None,
    scenario: str | None,
    model: str | None,
    no_cache: bool,
    refresh_cache: bool,
    cache_dir: Path | None,
    parallel: int | None,
    force: bool,
    no_retry_errors: bool,
    persist_traces: bool,
) -> None:
    """Wrap `python -m bench.run` with the stable CLI entry point."""

    if scenario is not None:
        raise unsupported("--scenario")
    if model is not None:
        raise unsupported("--model")
    if no_cache and refresh_cache:
        raise click.ClickException(
            "--no-cache and --refresh-cache are mutually exclusive"
        )
    if persist_traces:
        raise unsupported("--persist-traces")

    try:
        bundle_path = run_bundle(
            root=runs_dir_from_option(runs_dir),
            run_id=run_id,
            config_path=config,
            active_release=active_release,
            no_cache=no_cache,
            refresh_cache=refresh_cache,
            cache_dir=cache_dir,
            parallel=parallel,
            force=force,
            no_retry_errors=no_retry_errors,
            **(
                {}
                if config is not None
                else {
                    "turns": turns,
                    "mode": mode,
                    "run_seed": seed,
                    "epochs": epochs,
                }
            ),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(str(bundle_path))


@bench.command(help="Report on a benchmark bundle (#9).")
@click.argument("bundle", type=str)
@click.option("--runs-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    show_default=True,
)
@click.option("--metrics", type=str, default=None, help="Comma-separated metric names.")
@click.option("--by", type=str, default="aggregate", show_default=True)
def report(
    bundle: str,
    runs_dir: Path | None,
    output_format: str,
    metrics: str | None,
    by: str,
) -> None:
    """Print bundle reports in table, JSON, or CSV form."""

    if by != "aggregate":
        raise unsupported(f"--by {by}")
    bundle_path = resolve_bundle(bundle, runs_dir_from_option(runs_dir))
    metric_names = _parse_metrics(metrics)
    con = open_bundle(bundle_path)
    try:
        if output_format == "table":
            _print_table_report(con, bundle_path, metric_names)
        elif output_format == "json":
            click.echo(
                json.dumps(_json_report(con, bundle_path, metric_names), indent=2)
            )
        else:
            _print_csv_report(con, metric_names)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc


@bench.command(name="list", help="List available benchmark bundles (#9).")
@click.option("--runs-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--sort",
    "sort_key",
    type=click.Choice(["time", "cost", "bullwhip"]),
    default="time",
    show_default=True,
)
@click.option("--limit", type=int, default=20, show_default=True)
def list_bundles(runs_dir: Path | None, sort_key: str, limit: int) -> None:
    """List bundles in the resolved runs directory."""

    rows = [_bundle_row(path) for path in iter_bundles(runs_dir_from_option(runs_dir))]
    rows = [row for row in rows if row is not None]
    rows.sort(key=lambda row: _list_sort_key(row, sort_key), reverse=sort_key == "time")
    _echo_table(
        ["bundle", "run_id", "started", "models", "scenarios", "games", "total_cost"],
        [
            [
                row["bundle_id"],
                row["run_id"],
                row["started_at"] or "n/a",
                row["models"] or "n/a",
                row["scenarios"] or "n/a",
                str(row["games"]),
                _format_value(row["total_cost"]),
            ]
            for row in rows[:limit]
        ],
    )


@bench.command(help="Show games and per-game details for a bundle (#9).")
@click.argument("bundle", type=str)
@click.option("--runs-dir", type=click.Path(path_type=Path), default=None)
@click.option("--game", "game_id", type=str, default=None)
def show(bundle: str, runs_dir: Path | None, game_id: str | None) -> None:
    """Display a bundle summary or one game's timeline."""

    bundle_path = resolve_bundle(bundle, runs_dir_from_option(runs_dir))
    con = open_bundle(bundle_path)
    if game_id is None:
        rows = con.execute("""
            SELECT game_id, scenario_id, model, epoch, status, total_cost, wall_seconds
            FROM games
            ORDER BY epoch, game_id
            """).fetchall()
        _echo_table(
            [
                "game_id",
                "scenario",
                "model",
                "epoch",
                "status",
                "total_cost",
                "seconds",
            ],
            [
                [
                    row[0],
                    row[1],
                    row[2],
                    str(row[3]),
                    row[4],
                    _format_value(row[5]),
                    _format_value(row[6]),
                ]
                for row in rows
            ],
        )
        return

    game_exists = con.execute(
        "SELECT count(*) FROM games WHERE game_id = ?", [game_id]
    ).fetchone()[0]
    if not game_exists:
        raise click.ClickException(f"Game not found: {game_id}")
    click.echo("States")
    state_rows = con.execute(
        """
        SELECT week, role, inventory, backlog, order_placed, shipment_received,
               customer_demand, cost_week, cost_cum
        FROM states
        WHERE game_id = ?
        ORDER BY week, role
        """,
        [game_id],
    ).fetchall()
    _echo_table(
        [
            "week",
            "role",
            "inventory",
            "backlog",
            "order",
            "shipment",
            "demand",
            "cost",
            "cum",
        ],
        [[_format_value(value) for value in row] for row in state_rows],
    )
    click.echo()
    click.echo("Decisions")
    decision_rows = con.execute(
        """
        SELECT week, role, model_request, decision_int, parse_ok, latency_ms, cache_hit
        FROM decisions
        WHERE game_id = ?
        ORDER BY week, role
        """,
        [game_id],
    ).fetchall()
    _echo_table(
        ["week", "role", "model", "decision", "parse_ok", "latency_ms", "cache_hit"],
        [[_format_value(value) for value in row] for row in decision_rows],
    )


@bench.command(help="Compare models in a bundle; paired bootstrap lands in #15.")
@click.argument("bundle", required=False)
@click.option("--runs-dir", type=click.Path(path_type=Path), default=None)
@click.option("--baseline", type=str, default=None)
@click.option("--challenger", type=str, default=None)
def compare(
    bundle: str | None,
    runs_dir: Path | None,
    baseline: str | None,
    challenger: str | None,
) -> None:
    """Reserve the compare command shape for issue #15."""

    if bundle is not None:
        resolve_bundle(bundle, runs_dir_from_option(runs_dir))
    if not bundle or not baseline or not challenger:
        raise click.ClickException(
            "bench compare <bundle> --baseline X --challenger Y is reserved for #15"
        )
    raise click.ClickException("bench compare is reserved for #15")


def runs_dir_from_option(value: Path | None) -> Path:
    return runs_dir(value)


def _parse_metrics(metrics: str | None) -> list[str] | None:
    if metrics is None:
        return None
    names = [name.strip() for name in metrics.split(",") if name.strip()]
    return names or None


def _print_table_report(
    con: Any, bundle_path: Path, metric_names: list[str] | None
) -> None:
    if metric_names is None:
        text_report.print_report(con, bundle_path)
        return
    text_report.print_summary(con, bundle_path)
    click.echo()
    text_report.print_tokens(con)
    click.echo()
    text_report.print_latency(con)
    click.echo()
    _print_metrics(con, metric_names)


def _print_metrics(con: Any, metric_names: list[str]) -> None:
    if epoch_count(con) > 1:
        metrics = run_metric_reducers(con)
        unknown = sorted(set(metric_names) - set(metrics))
        if unknown:
            raise KeyError(f"Unknown metrics: {', '.join(unknown)}")
        rows = [
            [name, text_report._format_reduced_metric_value(name, metrics[name])]
            for name in metric_names
        ]
    else:
        metrics = run_metrics(con, metric_names)
        rows = [
            [name, text_report._format_metric_value(name, value)]
            for name, value in metrics.items()
        ]
    click.echo("Metrics")
    click.echo(text_report._format_table(["metric", "value"], rows))


def _json_report(
    con: Any, bundle_path: Path, metric_names: list[str] | None
) -> dict[str, Any]:
    return {
        "manifest": load_manifest(bundle_path),
        "metrics": _metric_payload(con, metric_names),
        "per_role": _per_role(con),
        "per_model": _per_model(con),
    }


def _metric_payload(con: Any, metric_names: list[str] | None) -> dict[str, Any]:
    if epoch_count(con) > 1:
        metrics = run_metric_reducers(con)
        selected = metric_names or list(metrics)
        unknown = sorted(set(selected) - set(metrics))
        if unknown:
            raise KeyError(f"Unknown metrics: {', '.join(unknown)}")
        return {
            name: {
                "value": metric.value,
                "error": metric.error,
                "n": metric.n,
                "values": metric.values,
            }
            for name, metric in metrics.items()
            if name in selected
        }
    return run_metrics(con, metric_names)


def _per_role(con: Any) -> list[dict[str, Any]]:
    rows = con.execute("""
        SELECT
          role,
          count(decisions.game_id) AS decisions,
          sum(input_tokens) AS input_tokens,
          sum(output_tokens) AS output_tokens,
          avg(latency_ms) AS mean_latency_ms,
          sum(cost_week) AS total_cost
        FROM decisions
        FULL OUTER JOIN states USING (run_id, game_id, week, role)
        GROUP BY role
        ORDER BY role
        """).fetchall()
    return [
        {
            "role": row[0],
            "decisions": row[1],
            "input_tokens": row[2],
            "output_tokens": row[3],
            "mean_latency_ms": row[4],
            "total_cost": row[5],
        }
        for row in rows
    ]


def _per_model(con: Any) -> list[dict[str, Any]]:
    rows = con.execute("""
        WITH game_summary AS (
          SELECT
            model,
            count(*) AS games,
            sum(total_cost) AS total_cost
          FROM games
          GROUP BY model
        ),
        decision_summary AS (
          SELECT
            model_request AS model,
            count(*) AS decisions,
            sum(input_tokens) AS input_tokens,
            sum(output_tokens) AS output_tokens,
            avg(latency_ms) AS mean_latency_ms
          FROM decisions
          GROUP BY model_request
        )
        SELECT
          game_summary.model,
          game_summary.games,
          game_summary.total_cost,
          coalesce(decision_summary.decisions, 0) AS decisions,
          decision_summary.input_tokens,
          decision_summary.output_tokens,
          decision_summary.mean_latency_ms
        FROM game_summary
        LEFT JOIN decision_summary USING (model)
        ORDER BY game_summary.model
        """).fetchall()
    return [
        {
            "model": row[0],
            "games": row[1],
            "total_cost": row[2],
            "decisions": row[3],
            "input_tokens": row[4],
            "output_tokens": row[5],
            "mean_latency_ms": row[6],
        }
        for row in rows
    ]


def _print_csv_report(con: Any, metric_names: list[str] | None) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(["metric", "value", "error", "n"])
    if epoch_count(con) > 1:
        metrics = _metric_payload(con, metric_names)
        for name, metric in metrics.items():
            writer.writerow([name, metric["value"], metric["error"], metric["n"]])
    else:
        for name, value in run_metrics(con, metric_names).items():
            writer.writerow([name, value, "", ""])


def _bundle_row(bundle_path: Path) -> dict[str, Any] | None:
    try:
        manifest = load_manifest(bundle_path)
        con = open_bundle(bundle_path)
        metrics = run_metrics(con)
        games = con.execute("SELECT count(*) FROM games").fetchone()[0]
    except Exception:
        return None
    models = ", ".join(model["id"] for model in manifest.get("models", []))
    return {
        "bundle_id": bundle_path.stem,
        "run_id": manifest.get("run_id") or bundle_path.stem,
        "started_at": manifest.get("started_at"),
        "models": models,
        "scenarios": ",".join(manifest.get("scenario_ids") or []),
        "games": games,
        "total_cost": metrics.get("total_cost"),
        "bullwhip_ratio": metrics.get("bullwhip_ratio"),
    }


def _list_sort_key(row: dict[str, Any], sort_key: str) -> Any:
    if sort_key == "time":
        return row["started_at"] or ""
    value = row["total_cost"] if sort_key == "cost" else row["bullwhip_ratio"]
    return (value is None, value if value is not None else 0)


def _echo_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        click.echo("  " + "  ".join(headers))
        return
    click.echo(text_report._format_table(headers, rows))


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    bench()
