"""Plain-text reports for Beer Game `.eval` bundles."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from src.bench.bundle import ROLE_NAMES
from src.bench.metrics import run_metrics
from src.bench.query import open_bundle


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print a Beer Game bundle report")
    parser.add_argument("bundle_path", type=Path, help="Path to a .eval bundle")
    args = parser.parse_args(argv)

    con = open_bundle(args.bundle_path)
    print_report(con, args.bundle_path)


def print_report(con: duckdb.DuckDBPyConnection, bundle_path: str | Path) -> None:
    """Print summary, token, and latency tables for an open bundle."""

    print_summary(con, bundle_path)
    print()
    print_tokens(con)
    print()
    print_latency(con)
    print()
    print_metrics(con)


def print_summary(con: duckdb.DuckDBPyConnection, bundle_path: str | Path) -> None:
    row = con.execute(
        "SELECT run_id, started_at, ended_at, scenario_ids FROM manifest"
    ).fetchone()
    if row is None:
        raise ValueError("manifest view is empty")

    run_id, started_at, ended_at, scenario_ids = row
    models = [
        value[0]
        for value in con.execute("SELECT unnest(models).id FROM manifest").fetchall()
    ]
    games = con.execute("SELECT count(*) FROM games").fetchone()[0]

    print(f"Bundle:      {bundle_path}")
    print(f"Run id:      {run_id}")
    print(f"Run started: {_format_timestamp(started_at)}")
    print(f"Run ended:   {_format_timestamp(ended_at)}")
    print(f"Wall time:   {_format_duration(started_at, ended_at)}")
    print(f"Models:      {', '.join(models) if models else 'n/a'}")
    print(f"Scenarios:   {len(scenario_ids or [])}")
    print(f"Games:       {games}")


def print_tokens(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("""
        SELECT
          model_request,
          role,
          sum(input_tokens) AS input_tokens,
          sum(output_tokens) AS output_tokens
        FROM decisions
        GROUP BY model_request, role
        ORDER BY model_request, role
        """).fetchall()

    grouped = _group_rows(rows)
    if not grouped:
        print("Tokens by role")
        print("  n/a")
        return

    for index, (model, model_rows) in enumerate(grouped.items()):
        if index:
            print()
        print(f"Tokens by role (model: {model})")
        print(
            _format_table(["role", "input", "output", "total"], _token_rows(model_rows))
        )


def print_latency(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("""
        SELECT
          model_request,
          role,
          avg(latency_ms) AS mean_ms,
          quantile_cont(latency_ms, 0.95) AS p95_ms
        FROM decisions
        GROUP BY model_request, role
        ORDER BY model_request, role
        """).fetchall()

    grouped = _group_rows(rows)
    if not grouped:
        print("Latency by role (mean / p95 in ms)")
        print("  n/a")
        return

    for index, (model, model_rows) in enumerate(grouped.items()):
        if index:
            print()
        print(f"Latency by role (model: {model}, mean / p95 in ms)")
        print(_format_table(["role", "mean", "p95"], _latency_rows(model_rows)))


def print_metrics(con: duckdb.DuckDBPyConnection) -> None:
    metrics = run_metrics(con)
    rows = [
        [name, _format_metric_value(name, value)] for name, value in metrics.items()
    ]
    print("Metrics")
    print(_format_table(["metric", "value"], rows))


def _group_rows(rows: list[tuple[Any, ...]]) -> dict[str, list[tuple[Any, ...]]]:
    grouped: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[0] or "n/a")].append(row)
    return dict(grouped)


def _token_rows(rows: list[tuple[Any, ...]]) -> list[list[str]]:
    by_role = {row[1]: row for row in rows}
    table_rows = []
    total_input = 0
    total_output = 0
    has_input = False
    has_output = False

    for role in ROLE_NAMES:
        row = by_role.get(role)
        input_tokens = row[2] if row is not None else None
        output_tokens = row[3] if row is not None else None
        if input_tokens is not None:
            total_input += input_tokens
            has_input = True
        if output_tokens is not None:
            total_output += output_tokens
            has_output = True
        table_rows.append(
            [
                role,
                _format_number(input_tokens),
                _format_number(output_tokens),
                _format_total(input_tokens, output_tokens),
            ]
        )

    table_rows.append(
        [
            "TOTAL",
            _format_number(total_input if has_input else None),
            _format_number(total_output if has_output else None),
            _format_total(
                total_input if has_input else None,
                total_output if has_output else None,
            ),
        ]
    )
    return table_rows


def _latency_rows(rows: list[tuple[Any, ...]]) -> list[list[str]]:
    by_role = {row[1]: row for row in rows}
    table_rows = []
    for role in ROLE_NAMES:
        row = by_role.get(role)
        mean_ms = row[2] if row is not None else None
        p95_ms = row[3] if row is not None else None
        table_rows.append(
            [
                role,
                _format_number(round(mean_ms) if mean_ms is not None else None),
                _format_number(round(p95_ms) if p95_ms is not None else None),
            ]
        )
    return table_rows


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    lines = [
        "  "
        + "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    ]
    for row in rows:
        lines.append(
            "  "
            + "  ".join(
                value.ljust(widths[index]) if index == 0 else value.rjust(widths[index])
                for index, value in enumerate(row)
            )
        )
    return "\n".join(lines)


def _format_timestamp(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(value)


def _format_duration(started_at: Any, ended_at: Any) -> str:
    if started_at is None or ended_at is None:
        return "n/a"
    if not isinstance(started_at, datetime) or not isinstance(ended_at, datetime):
        return "n/a"

    seconds = round((ended_at - started_at).total_seconds())
    if seconds < 0:
        return "n/a"
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def _format_number(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,}"


def _format_total(input_tokens: int | None, output_tokens: int | None) -> str:
    if input_tokens is None or output_tokens is None:
        return "n/a"
    return _format_number(input_tokens + output_tokens)


def _format_metric_value(name: str, value: Any) -> str:
    if value is None:
        return "n/a"
    if name == "recovery_time":
        return f"{value:g} weeks"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


if __name__ == "__main__":
    main()
