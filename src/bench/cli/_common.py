"""Shared helpers for the `bench` command."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click


def runs_dir(value: str | Path | None = None) -> Path:
    """Resolve the runs directory from CLI option, env var, or default."""

    candidate = (
        value or os.environ.get("BEERGAME_RUNS_DIR") or Path("/tmp/beer-game-runs")
    )
    return Path(candidate).expanduser().absolute()


def resolve_bundle(value: str | Path, root: str | Path | None = None) -> Path:
    """Resolve a bundle by full path, `latest`, or unique short prefix."""

    query = str(value)
    candidate = Path(query).expanduser()
    if candidate.is_dir():
        return candidate.resolve()
    if candidate.suffix == ".eval" or candidate.parent != Path("."):
        raise click.ClickException(f"Bundle directory not found: {candidate}")

    bundles = _bundle_dirs(runs_dir(root))
    if query == "latest":
        if not bundles:
            raise click.ClickException(f"No bundles found in {runs_dir(root)}")
        return max(bundles, key=_bundle_sort_key)

    matches = [
        path
        for path in bundles
        if path.stem.startswith(query) or path.name.startswith(query)
    ]
    if not matches:
        raise click.ClickException(
            f"No bundle matching '{query}' found in {runs_dir(root)}"
        )
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches[:5])
        suffix = "" if len(matches) <= 5 else f", ... ({len(matches)} total)"
        raise click.ClickException(
            f"Ambiguous bundle prefix '{query}': {names}{suffix}"
        )
    return matches[0]


def iter_bundles(root: str | Path | None = None) -> list[Path]:
    """Return valid-looking bundle directories under the resolved runs dir."""

    return _bundle_dirs(runs_dir(root))


def load_manifest(bundle_path: Path) -> dict[str, Any]:
    """Read a bundle manifest."""

    return json.loads((bundle_path / "manifest.json").read_text())


def unsupported(message: str) -> click.ClickException:
    """Return a consistent unsupported-feature error."""

    return click.ClickException(f"{message} is reserved for a follow-on issue")


def _bundle_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path.resolve()
        for path in root.glob("*.eval")
        if path.is_dir() and (path / "manifest.json").exists()
    )


def _bundle_sort_key(path: Path) -> tuple[str, float]:
    try:
        started_at = str(load_manifest(path).get("started_at") or "")
    except (OSError, json.JSONDecodeError):
        started_at = ""
    return (started_at, path.stat().st_mtime)
