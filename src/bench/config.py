"""Layered YAML config loader for Beer Game benchmark runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

RESERVED_LIST_POLICY = "_list_policy"
SECRET_KEYS = {"api_key", "authorization", "headers", "token", "secret"}


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    demand_pattern: str
    params: dict[str, Any] = Field(default_factory=dict)
    weeks: int = Field(gt=0)
    costs: dict[str, float]
    scenario_seed: int
    release_date: str | None = None
    removal_date: str | None = None


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    endpoint: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    context_window: int | None = None
    max_concurrent: int | None = None

    @model_validator(mode="after")
    def normalize_endpoint(self) -> "ModelConfig":
        if self.endpoint is None and self.base_url is not None:
            self.endpoint = self.base_url
        return self


class RunnerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parallel: int = Field(default=1, ge=1)
    persist_traces: bool = False


class CacheConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class TelemetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    otlp_endpoint: str | None = None


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    active_release: str = "2026-Q2"
    run_seed: int = 12345
    weeks: int = Field(default=36, gt=0)
    epochs: int = Field(default=1, ge=1)
    mode: Literal["mechanistic", "gabm"] = "mechanistic"
    runner: RunnerConfig = Field(default_factory=RunnerConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    scenarios: list[ScenarioConfig] = Field(default_factory=list)
    models: list[ModelConfig] = Field(default_factory=list)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)


def load_config(path: str | Path) -> dict[str, Any]:
    """Resolve and validate a layered YAML config file."""

    config_path = Path(path).expanduser().resolve()
    resolved = _resolve_file(config_path, [])
    _reject_secret_keys(resolved, config_path)
    try:
        model = RunConfig.model_validate(resolved)
    except ValidationError as exc:
        raise ValueError(f"Invalid config {config_path}: {exc}") from exc
    return _normalized_config(model)


def resolved_config_hash(cfg: dict[str, Any]) -> str:
    """Stable hash of a fully resolved config."""

    payload = json.dumps(
        cfg,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dicts, concatenating lists unless told to replace."""

    policy = _list_policy(override, base)
    result = {key: value for key, value in base.items() if key != RESERVED_LIST_POLICY}
    for key, value in override.items():
        if key == RESERVED_LIST_POLICY:
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif (
            key in result
            and isinstance(result[key], list)
            and isinstance(value, list)
            and policy.get(key, "concat") == "concat"
        ):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result


def _resolve_file(path: Path, stack: list[Path]) -> dict[str, Any]:
    if path in stack:
        cycle = " -> ".join(str(item) for item in [*stack, path])
        raise ValueError(f"Config import cycle detected: {cycle}")
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text())
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    resolved = _resolve_mapping(raw, path.parent, [*stack, path])
    if not isinstance(resolved, dict):
        raise ValueError(f"Config file must resolve to a mapping: {path}")
    return resolved


def _resolve_node(value: Any, base_dir: Path, stack: list[Path]) -> Any:
    if isinstance(value, dict):
        if not _has_config_directive(value):
            return {
                key: _resolve_node(item, base_dir, stack) for key, item in value.items()
            }
        return _resolve_mapping(value, base_dir, stack)
    if isinstance(value, list):
        return [_resolve_node(item, base_dir, stack) for item in value]
    return value


def _has_config_directive(value: dict[str, Any]) -> bool:
    return bool({"import", "default", "overwrite"} & set(value))


def _resolve_mapping(
    raw: dict[str, Any], base_dir: Path, stack: list[Path]
) -> dict[str, Any]:
    imported: dict[str, Any] = {}
    if "import" in raw:
        imports = raw["import"]
        import_paths = imports if isinstance(imports, list) else [imports]
        for import_path in import_paths:
            if not isinstance(import_path, str):
                raise ValueError(f"import values must be strings in {stack[-1]}")
            imported = deep_merge(
                imported, _resolve_file((base_dir / import_path).resolve(), stack)
            )

    default = _resolve_node(raw.get("default", {}), base_dir, stack)
    overwrite = _resolve_node(raw.get("overwrite", {}), base_dir, stack)
    if not isinstance(default, dict):
        raise ValueError(f"default must resolve to a mapping in {stack[-1]}")
    if not isinstance(overwrite, dict):
        raise ValueError(f"overwrite must resolve to a mapping in {stack[-1]}")

    local = {
        key: _resolve_node(value, base_dir, stack)
        for key, value in raw.items()
        if key not in {"import", "default", "overwrite"}
    }
    body = deep_merge(default, local)
    if RESERVED_LIST_POLICY in local:
        body[RESERVED_LIST_POLICY] = local[RESERVED_LIST_POLICY]
    merged = deep_merge(imported, body)
    return deep_merge(merged, overwrite)


def _list_policy(override: dict[str, Any], base: dict[str, Any]) -> dict[str, str]:
    raw = override.get(RESERVED_LIST_POLICY, {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("_list_policy must be a mapping")
    policy = {}
    for key, value in raw.items():
        if value not in {"concat", "replace"}:
            raise ValueError(f"_list_policy.{key} must be concat or replace")
        if key not in override and key not in base:
            raise ValueError(f"_list_policy references unknown key: {key}")
        policy[key] = value
    return policy


def _normalized_config(model: RunConfig) -> dict[str, Any]:
    data = model.model_dump(mode="json", exclude_none=True)
    for model_data in data.get("models", []):
        model_data.pop("base_url", None)
        if model_data.get("model") is None:
            model_data["model"] = model_data["id"]
    return data


def _reject_secret_keys(value: Any, path: Path, trail: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                location = ".".join((*trail, key))
                raise ValueError(
                    f"Secret-like config key is not allowed in {path}: {location}"
                )
            _reject_secret_keys(item, path, (*trail, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_keys(item, path, (*trail, str(index)))
