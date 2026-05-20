"""GABM (LLM-backed) decision strategy.

Each role is a distinct agent with a role-specific system prompt. The user
prompt on every turn includes the full player-visible history and a warning
against double-counting in-flight orders — the single error that drives the
bullwhip effect in novice human players.
"""

from __future__ import annotations

import os
from typing import Dict, List

from opentelemetry.trace import SpanKind, Status, StatusCode
from openai import OpenAI

from ..bench import telemetry
from ..bench.parser import max_plausible_order_from_env, parse_decision
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
        f"place an order to the {upstream}" if upstream else "set a production quantity"
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
        self.max_plausible_order = max_plausible_order_from_env()

    def decide(self, view: PlayerView) -> int:
        tracer = telemetry.get_tracer()
        provider = telemetry.provider_from_endpoint(self.endpoint)
        ctx = telemetry.get_decision_context()
        span_name = f"chat {self.model}"
        with tracer.start_as_current_span(span_name, kind=SpanKind.CLIENT) as span:
            _set_if(span, "gen_ai.operation.name", "chat")
            _set_if(span, "gen_ai.provider.name", provider)
            _set_if(span, "gen_ai.request.model", self.model)
            _set_if(span, "gen_ai.request.temperature", 0.4)
            for key, value in telemetry.server_attrs(self.endpoint).items():
                _set_if(span, key, value)
            _set_beergame_attrs(span, view, ctx)

            request_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": _user_prompt(view)},
                ],
                "temperature": 0.4,
                "max_tokens": 256,
                "timeout": 60,
            }
            if ctx and ctx.llm_seed is not None:
                request_kwargs["seed"] = ctx.llm_seed
                _set_if(span, "gen_ai.request.seed", ctx.llm_seed)

            try:
                response = self.client.chat.completions.create(**request_kwargs)
                _set_response_attrs(span, response)
                msg = _first_message(response)
                content = (getattr(msg, "content", None) or "").strip() if msg else ""
                reasoning = (
                    (getattr(msg, "reasoning", None) or "").strip() if msg else ""
                )
                result = parse_decision(
                    _answer_region(content, reasoning),
                    max_plausible_order=self.max_plausible_order,
                )
                decision = result.value if result.ok and result.value is not None else 0
                _set_if(span, "beergame.parse_ok", result.ok)
                _set_if(span, "beergame.parse_strategy", result.strategy)
                _set_if(span, "beergame.decision_int", decision)
                return decision
            except Exception as e:  # pragma: no cover - network error path
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                _set_if(span, "error.type", type(e).__name__)
                _set_if(span, "beergame.parse_ok", False)
                _set_if(span, "beergame.parse_strategy", "failed")
                _set_if(span, "beergame.decision_int", 0)
                print(f"[GABM:{self.role}] decision error: {e}; defaulting to 0")
                return 0


def _set_if(span, key: str, value) -> None:
    if value is not None:
        span.set_attribute(key, value)


def _set_beergame_attrs(
    span, view: PlayerView, ctx: telemetry.DecisionContext | None
) -> None:
    _set_if(span, "beergame.week", view.week)
    _set_if(span, "beergame.role", view.role.lower())
    if ctx is None:
        return
    _set_if(span, "beergame.run_id", ctx.run_id)
    _set_if(span, "beergame.game_id", ctx.game_id)
    _set_if(span, "beergame.scenario_id", ctx.scenario_id)
    _set_if(span, "beergame.scenario_release", ctx.scenario_release)
    _set_if(span, "beergame.epoch", ctx.epoch)
    _set_if(span, "beergame.cache_hit", ctx.cache_hit)
    _set_if(span, "beergame.context_used", ctx.context_used)
    _set_if(span, "beergame.context_window", ctx.context_window)


def _set_response_attrs(span, response) -> None:
    _set_if(span, "gen_ai.response.model", getattr(response, "model", None))
    _set_if(span, "gen_ai.response.id", getattr(response, "id", None))
    finish_reason = _first_finish_reason(response)
    if finish_reason is not None:
        span.set_attribute("gen_ai.response.finish_reasons", [finish_reason])

    usage = getattr(response, "usage", None)
    if usage is None:
        return
    _set_if(
        span,
        "gen_ai.usage.input_tokens",
        _get_first_attr(usage, "input_tokens", "prompt_tokens"),
    )
    _set_if(
        span,
        "gen_ai.usage.output_tokens",
        _get_first_attr(usage, "output_tokens", "completion_tokens"),
    )
    completion_details = getattr(usage, "completion_tokens_details", None)
    _set_if(
        span,
        "gen_ai.usage.reasoning.output_tokens",
        _get_first_attr(completion_details, "reasoning_tokens"),
    )
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    _set_if(
        span,
        "gen_ai.usage.cache_read.input_tokens",
        _get_first_attr(prompt_details, "cached_tokens"),
    )


def _get_first_attr(obj, *names: str):
    if obj is None:
        return None
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _first_message(response):
    choices = getattr(response, "choices", None) or []
    if not choices:
        return None
    return getattr(choices[0], "message", None)


def _first_finish_reason(response) -> str | None:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return None
    return getattr(choices[0], "finish_reason", None)


def _answer_region(content: str, reasoning: str) -> str:
    if content:
        if "</think>" in content:
            return content.rsplit("</think>", 1)[-1]
        return content
    return reasoning


_AGENTS: Dict[str, GABMAgent] = {}


def reset_state() -> None:
    """Reset cached agents; useful when env vars change between runs."""
    _AGENTS.clear()


def gabm_decision(view: PlayerView) -> int:
    if view.role not in _AGENTS:
        _AGENTS[view.role] = GABMAgent(view.role)
    return _AGENTS[view.role].decide(view)
