"""Mechanistic decision strategy: Sterman 1989 anchor-and-adjust.

Formulation::

    expected_demand_t = α_d * incoming_order + (1 - α_d) * expected_demand_{t-1}
    desired_IP        = S_inv + L * expected_demand_t
    adjustment        = β * (desired_IP - inventory + backlog - on_order)
    order             = max(0, expected_demand_t + adjustment)

Parameters use Sterman's defaults. ``L`` is 4 for Retailer/Wholesaler/Distributor
(2 weeks order delay + 2 weeks shipping delay) and 2 for Factory (production
delay only).

This strategy is stateful per role: it keeps a running `expected_demand`
smoother. We stash the state on the function object keyed by role name so the
decision fn remains ``(PlayerView) -> int`` at the call site.
"""

from dataclasses import dataclass
from typing import Dict

from ..engine.state import PlayerView


ALPHA_D = 0.36
BETA = 0.26
S_INV = 12


def _lead_time(role: str) -> int:
    return 2 if role == "Factory" else 4


@dataclass
class _RoleState:
    expected_demand: float = 4.0


def _get_state(role: str) -> _RoleState:
    cache: Dict[str, _RoleState] = getattr(sterman_decision, "_state", None)
    if cache is None:
        cache = {}
        sterman_decision._state = cache  # type: ignore[attr-defined]
    if role not in cache:
        cache[role] = _RoleState()
    return cache[role]


def reset_state() -> None:
    """Reset per-role smoothing state between simulation runs."""
    if hasattr(sterman_decision, "_state"):
        delattr(sterman_decision, "_state")


def sterman_decision(view: PlayerView) -> int:
    """Anchor-and-adjust decision rule (Sterman 1989)."""
    state = _get_state(view.role)
    L = _lead_time(view.role)

    state.expected_demand = (
        ALPHA_D * view.incoming_order + (1 - ALPHA_D) * state.expected_demand
    )

    desired_ip = S_INV + L * state.expected_demand
    inventory_gap = desired_ip - view.inventory + view.backlog - view.on_order
    adjustment = BETA * inventory_gap

    order = state.expected_demand + adjustment
    return max(0, int(round(order)))


# Keep a short alias matching the previous public name.
mechanistic_decision = sterman_decision
