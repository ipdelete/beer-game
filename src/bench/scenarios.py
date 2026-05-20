"""Scenario loading and release-date gating."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

RELEASE_RE = re.compile(r"^(\d{4})-Q([1-4])$")


def parse_release(value: str) -> tuple[int, int]:
    """Parse canonical `YYYY-Qn` release tags into sortable tuples."""

    match = RELEASE_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid release tag: {value!r}")
    return int(match.group(1)), int(match.group(2))


def load_scenarios(
    paths: list[str | Path], active_release: str | None = None
) -> list[dict[str, Any]]:
    """Load scenario YAML files and filter them by active release."""

    scenarios = [_load_scenario(Path(path).expanduser().resolve()) for path in paths]
    _, filtered = filter_scenarios(scenarios, active_release)
    return filtered


def filter_scenarios(
    scenarios: list[dict[str, Any]], active_release: str | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Filter resolved scenario dicts by release and removal dates."""

    if not scenarios:
        raise ValueError("No scenarios configured")
    for scenario in scenarios:
        _validate_scenario_release(scenario)

    selected_release = active_release or _latest_release(scenarios)
    active = parse_release(selected_release)
    filtered = [
        scenario for scenario in scenarios if _is_active_for_release(scenario, active)
    ]
    if not filtered:
        raise ValueError(f"No scenarios active for release {selected_release}")
    return selected_release, filtered


def _load_scenario(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario file must contain a mapping: {path}")
    try:
        _validate_scenario_release(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid scenario {path}: {exc}") from exc
    return raw


def _latest_release(scenarios: list[dict[str, Any]]) -> str:
    return max(
        (scenario["release_date"] for scenario in scenarios),
        key=parse_release,
    )


def _is_active_for_release(scenario: dict[str, Any], active: tuple[int, int]) -> bool:
    release = parse_release(scenario["release_date"])
    if release > active:
        return False
    removal_date = scenario.get("removal_date")
    if removal_date is None:
        return True
    return parse_release(removal_date) > active


def _validate_scenario_release(scenario: dict[str, Any]) -> None:
    release_date = scenario.get("release_date")
    if release_date is None:
        raise ValueError("scenario release_date is required")
    release = parse_release(release_date)
    removal_date = scenario.get("removal_date")
    if removal_date is not None and parse_release(removal_date) <= release:
        raise ValueError("scenario removal_date must be after release_date")
