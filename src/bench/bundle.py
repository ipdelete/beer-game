"""Writer for Beer Game `.eval` bundle directories."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA_VERSION = "1.0.0"

ROLE_NAMES = ("retailer", "wholesaler", "distributor", "factory")
ROLE_TITLES = tuple(role.title() for role in ROLE_NAMES)

DECISIONS_SCHEMA = pa.schema(
    [
        ("run_id", pa.string()),
        ("game_id", pa.string()),
        ("scenario_id", pa.string()),
        ("epoch", pa.int32()),
        ("week", pa.int32()),
        ("role", pa.string()),
        ("model_request", pa.string()),
        ("model_response", pa.string()),
        ("provider", pa.string()),
        ("temperature", pa.float64()),
        ("top_p", pa.float64()),
        ("seed_request", pa.int64()),
        ("input_tokens", pa.int64()),
        ("output_tokens", pa.int64()),
        ("reasoning_tokens", pa.int64()),
        ("cache_read_input_tokens", pa.int64()),
        ("finish_reason", pa.string()),
        ("response_id", pa.string()),
        ("latency_ms", pa.int64()),
        ("time_to_first_chunk_ms", pa.int64()),
        ("parse_ok", pa.bool_()),
        ("parse_strategy", pa.string()),
        ("decision_int", pa.int32()),
        ("context_used", pa.int64()),
        ("context_window", pa.int64()),
        ("cache_hit", pa.bool_()),
        ("error_type", pa.string()),
        ("raw_response_ref", pa.string()),
    ]
)

STATES_SCHEMA = pa.schema(
    [
        ("run_id", pa.string()),
        ("game_id", pa.string()),
        ("week", pa.int32()),
        ("role", pa.string()),
        ("inventory", pa.int32()),
        ("backlog", pa.int32()),
        ("order_placed", pa.int32()),
        ("shipment_received", pa.int32()),
        ("customer_demand", pa.int32()),
        ("cost_week", pa.float64()),
        ("cost_cum", pa.float64()),
    ]
)


def utc_now() -> str:
    """Return the current UTC timestamp in bundle JSON format."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_sortable_id(prefix: str | None = None) -> str:
    """Create a timestamp-prefixed id that sorts by creation time."""

    timestamp = utc_now().replace(":", "").replace("-", "")
    suffix = uuid.uuid4().hex[:10]
    return f"{timestamp}-{prefix}-{suffix}" if prefix else f"{timestamp}-{suffix}"


def stable_hash_int(parts: tuple[Any, ...]) -> int:
    """Hash structured values deterministically into a 32-bit integer."""

    payload = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    return int.from_bytes(hashlib.blake2b(payload, digest_size=8).digest(), "big") % (
        2**32
    )


def config_hash(config: dict[str, Any]) -> str:
    """Hash normalized run config for manifest provenance."""

    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def demand_hash(demand: list[int]) -> str:
    """Hash a materialized demand array for paired-run validation."""

    payload = json.dumps(demand, separators=(",", ":")).encode()
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


class BundleWriter:
    """Write one Beer Game `.eval` bundle directory."""

    def __init__(self, root: Path | str, run_id: str | None = None):
        self.root = Path(root)
        self.run_id = run_id or make_sortable_id("run")
        self.path = self.root / f"{self.run_id}.eval"
        self._manifest: dict[str, Any] | None = None
        self._decisions: list[dict[str, Any]] = []
        self._states: list[dict[str, Any]] = []

    def start(
        self,
        *,
        models: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> None:
        """Create the bundle directory and write initial manifest/scenarios."""

        self.path.mkdir(parents=True, exist_ok=False)
        (self.path / "traces").mkdir()

        self._manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "started_at": utc_now(),
            "ended_at": None,
            "git_sha": _git_sha(),
            "git_dirty": _git_dirty(),
            "prompt_version": None,
            "config_hash": config_hash(config),
            "config": config,
            "active_release": config["active_release"],
            "run_seed": config["run_seed"],
            "models": models,
            "scenario_ids": [scenario["scenario_id"] for scenario in scenarios],
            "tool_versions": {
                "beer-game": _project_version(),
                "python": sys.version.split()[0],
            },
        }
        self._write_json(self.path / "manifest.json", self._manifest)
        _write_jsonl(self.path / "scenarios.jsonl", scenarios, append=False)
        (self.path / "games.jsonl").write_text("")

    def append_game(self, game: dict[str, Any]) -> None:
        """Append one game metadata row to `games.jsonl`."""

        self._ensure_started()
        _write_jsonl(self.path / "games.jsonl", [game], append=True)

    def append_decisions(self, rows: list[dict[str, Any]]) -> None:
        """Buffer decision rows for `decisions.parquet`."""

        self._ensure_started()
        self._decisions.extend(rows)

    def append_states(self, rows: list[dict[str, Any]]) -> None:
        """Buffer state rows for `states.parquet`."""

        self._ensure_started()
        self._states.extend(rows)

    @property
    def started_at(self) -> str:
        """Return the manifest start timestamp after `start()`."""

        self._ensure_started()
        assert self._manifest is not None
        return self._manifest["started_at"]

    def finish(self) -> Path:
        """Write buffered Parquet files, finalize the manifest, and return path."""

        self._ensure_started()
        pq.write_table(
            pa.Table.from_pylist(self._decisions, schema=DECISIONS_SCHEMA),
            self.path / "decisions.parquet",
        )
        pq.write_table(
            pa.Table.from_pylist(self._states, schema=STATES_SCHEMA),
            self.path / "states.parquet",
        )
        assert self._manifest is not None
        self._manifest["ended_at"] = utc_now()
        self._write_json(self.path / "manifest.json", self._manifest)
        return self.path

    def _ensure_started(self) -> None:
        if self._manifest is None:
            raise RuntimeError("BundleWriter.start() must be called first")

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]], *, append: bool) -> None:
    mode = "a" if append else "w"
    with path.open(mode) as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def _git_sha() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _git_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip()) if result.returncode == 0 else False


def _project_version() -> str:
    try:
        import tomllib

        pyproject = Path("pyproject.toml")
        if pyproject.exists():
            return tomllib.loads(pyproject.read_text())["project"]["version"]
    except (KeyError, OSError, tomllib.TOMLDecodeError):
        pass
    return "unknown"
