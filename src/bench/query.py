"""DuckDB helpers for Beer Game `.eval` bundles."""

from __future__ import annotations

from glob import glob
from pathlib import Path
from typing import Callable

import duckdb

REQUIRED_BUNDLE_FILES = (
    "manifest.json",
    "scenarios.jsonl",
    "games.jsonl",
    "decisions.parquet",
    "states.parquet",
)


def open_bundle(path: str | Path) -> duckdb.DuckDBPyConnection:
    """Open one bundle and register canonical DuckDB views."""

    bundle_path = _validate_bundle_path(path)
    con = duckdb.connect()
    _register_views(con, [(bundle_path, None)])
    return con


def open_bundles(glob_pattern: str) -> duckdb.DuckDBPyConnection:
    """Open matching bundles and register unioned views with `bundle_id`.

    `bundle_id` is the bundle directory stem, without the `.eval` suffix.
    """

    bundle_paths = [
        _validate_bundle_path(path)
        for path in sorted(glob(glob_pattern))
        if Path(path).is_dir()
    ]
    if not bundle_paths:
        raise FileNotFoundError(f"No bundle directories matched: {glob_pattern}")

    con = duckdb.connect()
    _register_views(con, [(path, path.stem) for path in bundle_paths])
    return con


def _register_views(
    con: duckdb.DuckDBPyConnection, bundles: list[tuple[Path, str | None]]
) -> None:
    json_views = {
        "manifest": "manifest.json",
        "scenarios": "scenarios.jsonl",
        "games": "games.jsonl",
    }
    parquet_views = {
        "decisions": "decisions.parquet",
        "states": "states.parquet",
    }

    for view_name, filename in json_views.items():
        con.execute(
            f"CREATE VIEW {view_name} AS "
            + _union_sql(
                bundles,
                lambda path: f"read_json_auto({_sql_string(path / filename)}, union_by_name=true)",
            )
        )

    for view_name, filename in parquet_views.items():
        con.execute(
            f"CREATE VIEW {view_name} AS "
            + _union_sql(
                bundles,
                lambda path: f"read_parquet({_sql_string(path / filename)}, union_by_name=true)",
            )
        )


def _union_sql(
    bundles: list[tuple[Path, str | None]], source_sql: Callable[[Path], str]
) -> str:
    parts = []
    for path, bundle_id in bundles:
        prefix = "" if bundle_id is None else f"{_sql_string(bundle_id)} AS bundle_id, "
        parts.append(f"SELECT {prefix}* FROM {source_sql(path)}")
    return " UNION ALL BY NAME ".join(parts)


def _validate_bundle_path(path: str | Path) -> Path:
    bundle_path = Path(path).expanduser().resolve()
    if not bundle_path.is_dir():
        raise FileNotFoundError(f"Bundle directory not found: {bundle_path}")

    for filename in REQUIRED_BUNDLE_FILES:
        file_path = bundle_path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Bundle is missing {filename}: {bundle_path}")
        if file_path.stat().st_size == 0:
            raise ValueError(f"Bundle file is empty: {file_path}")

    return bundle_path


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"
