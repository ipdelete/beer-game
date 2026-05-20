"""Response cache for OpenAI-compatible GABM calls."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CACHE_DIR_ENV = "BEERGAME_CACHE_DIR"


@dataclass(frozen=True)
class CacheKey:
    base_url: str
    model: str
    temperature: float | None
    top_p: float | None
    llm_seed: int | None
    messages: list[dict[str, str]]
    scenario_id: str
    scenario_params_hash: str
    demand_hash: str
    prompt_version: str | None
    epoch: int

    def hash(self) -> str:
        payload = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        return hashlib.sha256(payload).hexdigest()


class ResponseCache:
    def __init__(
        self,
        root: Path | str | None = None,
        *,
        enabled: bool = True,
        refresh: bool = False,
    ):
        self.root = Path(
            root
            or os.environ.get(CACHE_DIR_ENV)
            or Path.home() / ".cache" / "beer-game"
        ).expanduser()
        self.enabled = enabled
        self.refresh = refresh
        if self.enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    def fetch(self, key: CacheKey) -> dict[str, Any] | None:
        if not self.enabled or self.refresh:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def store(self, key: CacheKey, response: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, prefix=f".{path.name}.", suffix=".tmp"
        ) as handle:
            json.dump(response, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, path)

    def _path(self, key: CacheKey) -> Path:
        return (
            self.root / "generate" / _safe_model_name(key.model) / f"{key.hash()}.json"
        )


def _safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model).strip("_") or "model"
