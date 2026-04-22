"""State structures exposed to decision functions.

Defines the player-visible state the engine passes to a decision function each
week. These are strict "what a human player sees" snapshots, so a decision
function cannot peek at upstream/downstream private state.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class PlayerRecord:
    """A single-week record of everything a player observes.

    Extends the classic `WeeklyRecord` with `incoming_order`, `shipment_received`,
    and `on_order` so a decision function (or GABM prompt) has enough context to
    reason about in-flight orders and avoid the phantom-ordering bullwhip trap.
    """

    week: int
    inventory: int
    backlog: int
    incoming_order: int
    shipment_received: int
    order_placed: int
    on_order: int
    cost: float


@dataclass
class PlayerView:
    """What a decision function sees for one role on one turn."""

    role: str
    week: int
    inventory: int
    backlog: int
    incoming_order: int
    shipment_received: int
    last_order_placed: int
    on_order: int
    history: List[PlayerRecord] = field(default_factory=list)
