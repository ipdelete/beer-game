"""Procedural customer-demand generators for benchmark scenarios."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.bench.bundle import stable_hash_int

DemandGenerator = Callable[[int, dict[str, Any], np.random.Generator], np.ndarray]


class ConstantParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int = Field(ge=0)


class StepParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: int = Field(ge=0)
    high: int = Field(ge=0)
    step_week: int = Field(ge=1)


class RampParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    start_week: int = Field(ge=1)
    end_week: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_weeks(self) -> "RampParams":
        if self.end_week < self.start_week:
            raise ValueError("end_week must be greater than or equal to start_week")
        return self


class SinusoidParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mean: float = Field(ge=0)
    amplitude: float = Field(ge=0)
    period_weeks: int = Field(gt=0)
    phase: float = 0


class BoundedRandomParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: int = Field(ge=0)
    high: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "BoundedRandomParams":
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        return self


PARAM_SCHEMAS = {
    "constant": ConstantParams,
    "step": StepParams,
    "ramp": RampParams,
    "sinusoid": SinusoidParams,
    "bounded_random": BoundedRandomParams,
}


def constant(
    weeks: int, params: dict[str, Any], rng: np.random.Generator
) -> np.ndarray:
    """params: {value: int >= 0}."""

    cfg = ConstantParams.model_validate(params)
    return np.full(weeks, cfg.value, dtype=int)


def step(weeks: int, params: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    """params: {low: int >= 0, high: int >= 0, step_week: int >= 1}."""

    cfg = StepParams.model_validate(params)
    week_numbers = np.arange(1, weeks + 1)
    return np.where(week_numbers < cfg.step_week, cfg.low, cfg.high).astype(int)


def ramp(weeks: int, params: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    """params: {start: int >= 0, end: int >= 0, start_week: int >= 1, end_week: int >= start_week}."""

    cfg = RampParams.model_validate(params)
    week_numbers = np.arange(1, weeks + 1)
    if cfg.start_week == cfg.end_week:
        values = np.where(week_numbers < cfg.start_week, cfg.start, cfg.end)
    else:
        values = np.interp(
            week_numbers,
            [cfg.start_week, cfg.end_week],
            [cfg.start, cfg.end],
        )
    return np.rint(np.clip(values, 0, None)).astype(int)


def sinusoid(
    weeks: int, params: dict[str, Any], rng: np.random.Generator
) -> np.ndarray:
    """params: {mean: float >= 0, amplitude: float >= 0, period_weeks: int > 0, phase: float = 0}."""

    cfg = SinusoidParams.model_validate(params)
    t = np.arange(weeks)
    values = cfg.mean + cfg.amplitude * np.sin(
        2 * np.pi * (t - cfg.phase) / cfg.period_weeks
    )
    return np.rint(np.clip(values, 0, None)).astype(int)


def bounded_random(
    weeks: int, params: dict[str, Any], rng: np.random.Generator
) -> np.ndarray:
    """params: {low: int >= 0, high: int >= low}; discrete uniform in [low, high]."""

    cfg = BoundedRandomParams.model_validate(params)
    return rng.integers(cfg.low, cfg.high + 1, size=weeks, dtype=int)


GENERATORS: dict[str, DemandGenerator] = {
    "constant": constant,
    "step": step,
    "ramp": ramp,
    "sinusoid": sinusoid,
    "bounded_random": bounded_random,
}


def validate_demand_params(pattern: str, params: dict[str, Any]) -> None:
    """Validate pattern-specific scenario params."""

    if pattern not in PARAM_SCHEMAS:
        raise ValueError(f"Unknown demand_pattern: {pattern}")
    PARAM_SCHEMAS[pattern].model_validate(params)


def materialize_demand(scenario: dict, run_seed: int, epoch: int) -> np.ndarray:
    """Materialize one scenario's customer-demand sequence."""

    pattern = scenario["demand_pattern"]
    if pattern not in GENERATORS:
        raise ValueError(f"Unknown demand_pattern: {pattern}")
    weeks = int(scenario["weeks"])
    seed = stable_hash_int(
        (run_seed, scenario["scenario_id"], scenario["scenario_seed"], epoch)
    )
    demand = GENERATORS[pattern](
        weeks, scenario.get("params", {}), np.random.default_rng(seed)
    )
    if len(demand) != weeks:
        raise ValueError(
            f"Demand generator {pattern} returned {len(demand)} weeks; expected {weeks}"
        )
    return demand.astype(int, copy=False)
