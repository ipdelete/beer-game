"""GABM (LLM-backed) decision strategy.

Each role is a distinct agent with a role-specific system prompt. The user
prompt on every turn includes the full player-visible history and a warning
against double-counting in-flight orders — the single error that drives the
bullwhip effect in novice human players.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List

from openai import OpenAI

from ..engine.state import PlayerRecord, PlayerView


DEFAULT_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODEL = "mistral:latest"


_DOWNSTREAM = {
    "Retailer": "customer",
    "Wholesaler": "Retailer",
    "Distributor": "Wholesaler",
    "Factory": "Distributor",
}
_UPSTREAM = {
    "Retailer": "Wholesaler",
    "Wholesaler": "Distributor",
    "Distributor": "Factory",
    "Factory": None,  # Factory produces; no upstream
}


def _system_prompt(role: str) -> str:
    upstream = _UPSTREAM[role]
    downstream = _DOWNSTREAM[role]
    target_text = (
        f"place an order to the {upstream}"
        if upstream
        else "set a production quantity"
    )
    return (
        f"You are the {role} in a 4-tier beer distribution supply chain. "
        "Your goal is to minimize total cost over the game. "
        "Inventory costs $0.50 per case per week; backlog costs $1.00 per case per week. "
        f"You cannot communicate with the other tiers. Each week you must {target_text}. "
        f"You observe orders only from your immediate downstream partner (the {downstream}). "
        "IMPORTANT — avoid double-ordering: remember the orders you have already placed are "
        "still in the pipeline (see 'on_order'). Ordering to cover your entire backlog every "
        "week when earlier orders are still en route is the classic bullwhip mistake. "
        "Anchor your order on recent incoming demand and adjust gently for the gap between "
        "desired inventory position (≈ 12 + L × demand) and actual position "
        "(inventory − backlog + on_order)."
    )


def _history_table(history: List[PlayerRecord]) -> str:
    if not history:
        return "(no prior weeks)"
    header = "Week | Inv | Backlog | IncomingOrder | ShipmentRcvd | OrderPlaced | OnOrder | Cost"
    rows = [header, "-" * len(header)]
    for r in history:
        rows.append(
            f"{r.week:>4} | {r.inventory:>3} | {r.backlog:>7} | "
            f"{r.incoming_order:>13} | {r.shipment_received:>12} | "
            f"{r.order_placed:>11} | {r.on_order:>7} | {r.cost:>5.2f}"
        )
    return "\n".join(rows)


def _user_prompt(view: PlayerView) -> str:
    return (
        f"Week: {view.week}\n"
        f"Role: {view.role}\n"
        f"Current inventory: {view.inventory}\n"
        f"Current backlog: {view.backlog}\n"
        f"Incoming order this week (from {_DOWNSTREAM[view.role]}): {view.incoming_order}\n"
        f"Shipment received this week: {view.shipment_received}\n"
        f"Last order you placed: {view.last_order_placed}\n"
        f"Orders still in pipeline (on_order): {view.on_order}\n\n"
        f"History:\n{_history_table(view.history)}\n\n"
        "How many cases should you order this week?\n"
        "Respond with ONLY a single non-negative integer."
    )


class GABMAgent:
    def __init__(self, role: str):
        self.role = role
        self.endpoint = os.getenv("LLM_ENDPOINT", DEFAULT_ENDPOINT)
        self.model = os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(base_url=self.endpoint, api_key="ollama")
        self.system_prompt = _system_prompt(role)

    def decide(self, view: PlayerView) -> int:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": _user_prompt(view)},
                ],
                temperature=0.4,
                max_tokens=256,
                timeout=60,
            )
            msg = response.choices[0].message
            content = (msg.content or "").strip()
            # Reasoning models (e.g. gpt-oss) sometimes return their final answer
            # in `reasoning` rather than `content`; fall back to that if empty.
            if not content:
                reasoning = getattr(msg, "reasoning", None) or ""
                content = reasoning.strip()
            # Use the LAST integer in the response. Reasoning chains often cite
            # earlier numbers (incoming order, inventory, etc.); the final
            # committed number is almost always at the end.
            matches = re.findall(r"-?\d+", content)
            if matches:
                return max(0, int(matches[-1]))
            return 0
        except Exception as e:  # pragma: no cover - network error path
            print(f"[GABM:{self.role}] decision error: {e}; defaulting to 0")
            return 0


_AGENTS: Dict[str, GABMAgent] = {}


def reset_state() -> None:
    """Reset cached agents; useful when env vars change between runs."""
    _AGENTS.clear()


def gabm_decision(view: PlayerView) -> int:
    if view.role not in _AGENTS:
        _AGENTS[view.role] = GABMAgent(view.role)
    return _AGENTS[view.role].decide(view)
