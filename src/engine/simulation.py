"""Beer Game orchestration engine.

Owns four `BaseRole` instances (Retailer, Wholesaler, Distributor, Factory),
runs the canonical Sterman two-phase week, and routes shipments between roles.
The per-week logic is:

    1. Snapshot `slots[0]` on every delay pipeline (arrivals this week)
    2. For each role, build a `PlayerView` from that snapshot
    3. Call the pluggable `decision_fn(PlayerView)` for all 4 roles
    4. Execute each role's `execute_week(...)` with its decision
    5. Wire Factory output into Distributor's incoming shipping delay,
       Distributor -> Wholesaler, Wholesaler -> Retailer
    6. Append a `PlayerRecord` to each role's history

The decision function is pure: `(PlayerView) -> int`. It has no access to
anything a real player couldn't see.
"""

from typing import Callable, Dict, List, Sequence

import sys
from pathlib import Path

# Make sibling `roles` package importable when engine is imported as `src.engine`
_repo_src = Path(__file__).resolve().parent.parent
if str(_repo_src) not in sys.path:
    sys.path.insert(0, str(_repo_src))

from roles import Retailer, Wholesaler, Distributor, Factory  # noqa: E402

from .state import PlayerRecord, PlayerView  # noqa: E402

DecisionFn = Callable[[PlayerView], int]


class BeerGameEngine:
    """Orchestrates a classic Beer Game using pluggable decision functions."""

    def __init__(
        self,
        decision_fn: DecisionFn,
        team_name: str = "Beer Game",
        customer_demand: Sequence[int] | None = None,
    ):
        self.team_name = team_name
        self.decision_fn = decision_fn

        self.retailer = Retailer(team_name)
        if customer_demand is not None:
            self.retailer.customer_orders = [int(value) for value in customer_demand]
        self.wholesaler = Wholesaler(team_name)
        self.distributor = Distributor(team_name)
        self.factory = Factory(team_name)

        self.current_week = 0
        self.history: Dict[str, List[PlayerRecord]] = {
            "Retailer": [],
            "Wholesaler": [],
            "Distributor": [],
            "Factory": [],
        }
        self.order_history: Dict[str, List[int]] = {
            "Customer": [],
            "Retailer": [],
            "Wholesaler": [],
            "Distributor": [],
            "Factory": [],
        }

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _slot0(pipeline) -> int:
        if pipeline is None:
            return 0
        slots = pipeline.slots
        return slots[0] if slots else 0

    def _on_order(self, role) -> int:
        """Total units already ordered but not yet in inventory.

        For retailer/wholesaler/distributor, that's orders in the upstream
        order-delay PLUS shipments in the incoming shipping-delay. For the
        factory it's just production in the production pipeline.
        """
        if role is self.factory:
            return self.factory.production_delay.get_total()
        order_pipeline_total = (
            role.outgoing_order_delay.get_total() if role.outgoing_order_delay else 0
        )
        return order_pipeline_total + role.incoming_shipping_delay.get_total()

    def _build_view(
        self,
        role,
        role_name: str,
        week: int,
        incoming_order: int,
        shipment_arriving: int,
    ) -> PlayerView:
        return PlayerView(
            role=role_name,
            week=week,
            inventory=role.inventory,
            backlog=role.backlog,
            incoming_order=incoming_order,
            shipment_received=shipment_arriving,
            last_order_placed=role.last_order_placed,
            on_order=self._on_order(role),
            history=list(self.history[role_name]),
        )

    # ── main loop ──────────────────────────────────────────────────────────

    def simulate_week(self) -> None:
        self.current_week += 1
        week = self.current_week

        # Phase 1: snapshot what arrives this week from each pipeline.
        # Orders arriving at each upstream role from their downstream partner:
        retailer_out_order_arriving = self._slot0(self.retailer.outgoing_order_delay)
        wholesaler_out_order_arriving = self._slot0(
            self.wholesaler.outgoing_order_delay
        )
        distributor_out_order_arriving = self._slot0(
            self.distributor.outgoing_order_delay
        )
        # Beer shipments arriving at each role this week:
        retailer_beer_arriving = self._slot0(self.retailer.incoming_shipping_delay)
        wholesaler_beer_arriving = self._slot0(self.wholesaler.incoming_shipping_delay)
        distributor_beer_arriving = self._slot0(
            self.distributor.incoming_shipping_delay
        )
        factory_beer_arriving = self._slot0(self.factory.production_delay)

        customer_order = self.retailer.get_customer_order(week)

        # Phase 2: build views + decisions from that snapshot.
        # Incoming orders per role *as they will be processed this week*:
        #   - Retailer fills customer_order directly (from outside the chain)
        #   - Wholesaler sees retailer's order that is *arriving* now
        #   - Distributor sees wholesaler's order that is arriving now
        #   - Factory sees distributor's order that is arriving now
        retailer_view = self._build_view(
            self.retailer,
            "Retailer",
            week,
            incoming_order=customer_order,
            shipment_arriving=retailer_beer_arriving,
        )
        wholesaler_view = self._build_view(
            self.wholesaler,
            "Wholesaler",
            week,
            incoming_order=retailer_out_order_arriving,
            shipment_arriving=wholesaler_beer_arriving,
        )
        distributor_view = self._build_view(
            self.distributor,
            "Distributor",
            week,
            incoming_order=wholesaler_out_order_arriving,
            shipment_arriving=distributor_beer_arriving,
        )
        factory_view = self._build_view(
            self.factory,
            "Factory",
            week,
            incoming_order=distributor_out_order_arriving,
            shipment_arriving=factory_beer_arriving,
        )

        retailer_decision = max(0, int(self.decision_fn(retailer_view)))
        wholesaler_decision = max(0, int(self.decision_fn(wholesaler_view)))
        distributor_decision = max(0, int(self.decision_fn(distributor_view)))
        factory_decision = max(0, int(self.decision_fn(factory_view)))

        # Phase 3: execute all roles (advances delays, updates inventory/backlog).
        self.retailer.execute_week(
            order_decision=retailer_decision, customer_order=customer_order
        )
        wholesaler_shipped = self.wholesaler.execute_week(
            incoming_order=retailer_out_order_arriving,
            order_decision=wholesaler_decision,
        )
        distributor_shipped = self.distributor.execute_week(
            incoming_order=wholesaler_out_order_arriving,
            order_decision=distributor_decision,
        )
        factory_shipped = self.factory.execute_week(
            incoming_order=distributor_out_order_arriving,
            production_decision=factory_decision,
        )

        # Phase 4: wire shipments into downstream shipping delays.
        if wholesaler_shipped > 0:
            self.retailer.incoming_shipping_delay.add_input(wholesaler_shipped)
        if distributor_shipped > 0:
            self.wholesaler.incoming_shipping_delay.add_input(distributor_shipped)
        if factory_shipped > 0:
            self.distributor.incoming_shipping_delay.add_input(factory_shipped)

        # Phase 5: append PlayerRecord rows for history and exporter.
        self._record(
            "Retailer",
            week,
            self.retailer,
            customer_order,
            retailer_beer_arriving,
            retailer_decision,
        )
        self._record(
            "Wholesaler",
            week,
            self.wholesaler,
            retailer_out_order_arriving,
            wholesaler_beer_arriving,
            wholesaler_decision,
        )
        self._record(
            "Distributor",
            week,
            self.distributor,
            wholesaler_out_order_arriving,
            distributor_beer_arriving,
            distributor_decision,
        )
        self._record(
            "Factory",
            week,
            self.factory,
            distributor_out_order_arriving,
            factory_beer_arriving,
            factory_decision,
        )

        # Track flat order history (compat with legacy analysis tooling).
        self.order_history["Customer"].append(customer_order)
        self.order_history["Retailer"].append(retailer_decision)
        self.order_history["Wholesaler"].append(wholesaler_decision)
        self.order_history["Distributor"].append(distributor_decision)
        self.order_history["Factory"].append(factory_decision)

    def _record(
        self,
        role_name: str,
        week: int,
        role,
        incoming_order: int,
        shipment_received: int,
        order_placed: int,
    ) -> None:
        cost = role.get_current_cost()
        record = PlayerRecord(
            week=week,
            inventory=role.inventory,
            backlog=role.backlog,
            incoming_order=incoming_order,
            shipment_received=shipment_received,
            order_placed=order_placed,
            on_order=self._on_order(role),
            cost=cost,
        )
        self.history[role_name].append(record)

    # ── convenience ────────────────────────────────────────────────────────

    def get_total_costs(self) -> Dict[str, float]:
        return {
            name: role.get_total_cost()
            for name, role in (
                ("Retailer", self.retailer),
                ("Wholesaler", self.wholesaler),
                ("Distributor", self.distributor),
                ("Factory", self.factory),
            )
        }
