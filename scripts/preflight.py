"""One-shot decode test per tournament model.

Exercises the *real* GABM agent decode path (system prompt, user prompt,
reasoning-field fallback, last-integer extraction) against each candidate
model using a realistic mid-game PlayerView. Reports latency + parsed
integer so we can catch misbehaving models before the full tournament.

The model roster can be overridden with the ``MODELS`` env var
(space-separated). The endpoint is taken from ``LLM_ENDPOINT``
(default: Ollama at ``http://localhost:11434/v1``). A connectivity
probe against ``GET {endpoint}/models`` runs first so wrong endpoints
fail fast instead of inside the per-model decode loop.
"""
from __future__ import annotations

import os
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.state import PlayerView, PlayerRecord  # noqa: E402
from src.gabm.agent import GABMAgent  # noqa: E402

DEFAULT_MODELS = [
    "mistral:latest",
    "qwen3.5:9b",
    "phi4:14b",
    "gemma4:e4b-it-q4_K_M",
    "gpt-oss:20b",
]

MODELS = os.environ.get("MODELS", "").split() or DEFAULT_MODELS


def build_view() -> PlayerView:
    """Plausible mid-game state for a Wholesaler around week 8."""
    history = [
        PlayerRecord(week=w, inventory=12 - w, backlog=0,
                     incoming_order=4, shipment_received=4,
                     order_placed=4, on_order=8, cost=(12 - w) * 0.5)
        for w in range(1, 5)
    ] + [
        PlayerRecord(week=w, inventory=max(0, 8 - (w - 5) * 2),
                     backlog=max(0, (w - 5) * 2),
                     incoming_order=8, shipment_received=4,
                     order_placed=8, on_order=16, cost=0)
        for w in range(5, 9)
    ]
    return PlayerView(
        role="Wholesaler",
        week=9,
        inventory=2,
        backlog=6,
        incoming_order=8,
        shipment_received=4,
        last_order_placed=8,
        on_order=16,
        history=history,
    )


def main() -> int:
    view = build_view()
    endpoint = os.environ.get('LLM_ENDPOINT', 'http://localhost:11434/v1')
    print(f"Preflight: one decode per model using a realistic week-9 Wholesaler view.")
    print(f"Endpoint : {endpoint}")
    print(f"Models   : {' '.join(MODELS)}")

    # Connectivity probe: hit /models so wrong endpoints fail fast.
    probe_url = endpoint.rstrip('/') + '/models'
    try:
        with urlopen(probe_url, timeout=5) as resp:
            print(f"Probe    : {probe_url} -> HTTP {resp.status}")
    except URLError as e:
        print(f"Probe    : {probe_url} -> FAILED ({e.reason}); aborting.")
        return 2
    except Exception as e:
        print(f"Probe    : {probe_url} -> FAILED ({type(e).__name__}: {e}); aborting.")
        return 2

    print(f"{'MODEL':<28}  {'SECONDS':>8}  {'ORDER':>6}  VERDICT")
    print("-" * 70)

    failures = 0
    for model in MODELS:
        os.environ["LLM_MODEL"] = model
        agent = GABMAgent("Wholesaler")
        t0 = time.time()
        try:
            order = agent.decide(view)
            elapsed = time.time() - t0
            ok = isinstance(order, int) and 0 <= order <= 200
            verdict = "ok" if ok else f"suspect value={order}"
            if not ok:
                failures += 1
            print(f"{model:<28}  {elapsed:>8.2f}  {order:>6}  {verdict}")
        except Exception as e:
            elapsed = time.time() - t0
            failures += 1
            print(f"{model:<28}  {elapsed:>8.2f}  {'ERR':>6}  {type(e).__name__}: {e}")

    print("-" * 70)
    print(f"{'PASS' if failures == 0 else f'{failures} FAILURE(S)'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
