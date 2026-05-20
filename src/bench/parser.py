"""Shared parser for LLM beer-game order decisions."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

MAX_PLAUSIBLE_ORDER = 1000
MAX_PLAUSIBLE_ORDER_ENV = "BEERGAME_MAX_PLAUSIBLE_ORDER"


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing a model response into an order decision."""

    value: int | None
    strategy: str
    ok: bool


StrategyFn = Callable[[str], int]


def _strict_int(raw: str) -> int:
    """Parse only responses that are exactly one integer after whitespace trim."""

    return int(raw.strip())


def _json_field(raw: str) -> int:
    """Parse top-level JSON with an `order` field."""

    payload = json.loads(raw)
    return int(payload["order"])


def _boxed(raw: str) -> int:
    """Parse LaTeX-style `\\boxed{N}` answers."""

    return int(_required_match(r"\\boxed\{\s*(-?\d+)\s*\}", raw).group(1))


def _solution_tag(raw: str) -> int:
    """Parse `<solution>N</solution>` tags, case-insensitively."""

    return int(
        _required_match(
            r"<solution>\s*(-?\d+)\s*</solution>", raw, flags=re.IGNORECASE | re.DOTALL
        ).group(1)
    )


def _answer_tag(raw: str) -> int:
    """Parse `<answer>N</answer>` tags, case-insensitively."""

    return int(
        _required_match(
            r"<answer>\s*(-?\d+)\s*</answer>", raw, flags=re.IGNORECASE | re.DOTALL
        ).group(1)
    )


def _last_line_int(raw: str) -> int:
    """Parse the first integer on the final non-empty line."""

    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ValueError("no non-empty lines")
    return int(_required_match(r"-?\d+", lines[-1]).group())


def _first_int_anywhere(raw: str) -> int:
    """Parse the first integer anywhere in the response."""

    return int(_required_match(r"-?\d+", raw).group())


STRATEGIES: tuple[tuple[str, StrategyFn], ...] = (
    ("strict_int", _strict_int),
    ("json_field", _json_field),
    ("boxed", _boxed),
    ("solution_tag", _solution_tag),
    ("answer_tag", _answer_tag),
    ("last_line_int", _last_line_int),
    ("first_int_anywhere", _first_int_anywhere),
)


def parse_decision(
    raw: str, max_plausible_order: int = MAX_PLAUSIBLE_ORDER
) -> ParseResult:
    """Parse a raw model response using ordered fallback strategies.

    The function is pure: callers that want environment configuration should
    resolve it before calling.
    """

    for name, strategy in STRATEGIES:
        try:
            value = strategy(raw)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        ok = 0 <= value <= max_plausible_order
        return ParseResult(value=value, strategy=name, ok=ok)
    return ParseResult(value=None, strategy="failed", ok=False)


def max_plausible_order_from_env(
    env: Mapping[str, str] | None = None,
) -> int:
    """Return the plausible-order bound configured by environment."""

    values = os.environ if env is None else env
    raw = values.get(MAX_PLAUSIBLE_ORDER_ENV)
    if raw is None:
        return MAX_PLAUSIBLE_ORDER
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{MAX_PLAUSIBLE_ORDER_ENV} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{MAX_PLAUSIBLE_ORDER_ENV} must be non-negative")
    return value


def _required_match(pattern: str, raw: str, *, flags: int = 0) -> re.Match[str]:
    match = re.search(pattern, raw, flags)
    if match is None:
        raise ValueError("pattern not found")
    return match
