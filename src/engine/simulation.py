from typing import List, Dict, Callable
from .state import GameState, PositionState


class DelayQueue:
    """A FIFO delay queue for items arriving after a number of turns."""

    def __init__(self, delay: int = 2):
        self.delay = delay
        self.queue: List[dict] = []

    def enqueue(self, turn: int, amount: int) -> None:
        self.queue.append({"arrival_turn": turn + self.delay, "amount": amount})
        self.queue.sort(key=lambda x: x["arrival_turn"])

    def dequeue(self, turn: int) -> int:
        total = 0
        remaining: List[dict] = []
        for item in self.queue:
            if item["arrival_turn"] == turn:
                total += int(item["amount"])
            else:
                remaining.append(item)
        self.queue = remaining
        return total


class BeerGameSimulation:
    def __init__(
        self,
        state: GameState,
        decision_fn: Callable[[str, PositionState, int, int, int], int],
    ):
        """Initialize simulation.

        Args:
            state: The GameState to operate on.
            decision_fn: Called with (role, state, customer_demand, turn, incoming_order).
        """
        self.state = state
        self.decision_fn = decision_fn
        self.order_delay: Dict[str, DelayQueue] = {
            "Wholesaler": DelayQueue(1),
            "Distributor": DelayQueue(1),
            "Factory": DelayQueue(1),
        }
        self.shipping_delay: Dict[str, DelayQueue] = {
            "Retailer": DelayQueue(1),
            "Wholesaler": DelayQueue(1),
            "Distributor": DelayQueue(1),
            "Factory": DelayQueue(1),
        }
        self.flow_map: Dict[str, str] = {
            "Retailer": "Wholesaler",
            "Wholesaler": "Distributor",
            "Distributor": "Factory",
        }

    def _ship_amount(self, upstream_pos: PositionState, order_amount: int) -> int:
        """Ship as much as possible from upstream_pos; return actual shipped."""
        to_fill = order_amount + upstream_pos.backlog
        if upstream_pos.inventory >= to_fill:
            shipped = to_fill
            upstream_pos.inventory -= shipped
            upstream_pos.backlog = 0
        else:
            shipped = upstream_pos.inventory
            upstream_pos.backlog = to_fill - shipped
            upstream_pos.inventory = 0
        return shipped

    def run_turn(self) -> Dict[str, int]:
        self.state.current_turn += 1
        turn = self.state.current_turn

        if turn == 5:
            self.state.customer_demand = 8

        orders_placed: Dict[str, int] = {}
        shipment_received_map: Dict[str, int] = {}

        role_order = ["Retailer", "Wholesaler", "Distributor", "Factory"]

        # Step 1: Collect order decisions
        for role in role_order:
            pos = self.state.positions[role]

            # Receive shipments arriving this turn
            sr = self.shipping_delay[role].dequeue(turn)
            shipment_received_map[role] = sr
            pos.inventory += sr

            # Determine incoming order from downstream
            if role == "Retailer":
                incoming_order = self.state.customer_demand
            else:
                idx = role_order.index(role)
                downstream = role_order[idx - 1]
                incoming_order = orders_placed[downstream]

            # Get order decision from agent
            customer_demand = self.state.customer_demand if role == "Retailer" else 0
            order = self.decision_fn(role, pos, customer_demand, turn, incoming_order)
            order = max(0, order)
            orders_placed[role] = order

        # Step 2: Fulfill orders, compute costs, record history
        for role in role_order:
            pos = self.state.positions[role]

            if role == "Retailer":
                incoming_order = self.state.customer_demand
            else:
                idx = role_order.index(role)
                downstream = role_order[idx - 1]
                incoming_order = orders_placed[downstream]

            self._ship_amount(pos, incoming_order)
            pos.total_cost += (pos.inventory * 0.50) + (pos.backlog * 1.00)
            pos.update_history(turn, orders_placed[role], shipment_received_map[role])

        # Step 3: Ship orders upstream (with delay)
        for downstream, upstream in self.flow_map.items():
            self.order_delay[upstream].enqueue(turn, orders_placed[downstream])

        # Step 4: Ship production from Factory
        self.shipping_delay["Factory"].enqueue(turn, orders_placed["Factory"])

        return orders_placed
