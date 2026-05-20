"""Retailer role implementation for the Beer Game."""

from typing import List, Optional
from .base_role import BaseRole


class Retailer(BaseRole):
    """
    Retailer role in the Beer Game.

    The retailer:
    - Receives customer orders directly
    - Ships to customers
    - Orders from the Wholesaler
    - Is the only position that knows actual customer demand
    """

    def __init__(self, team_name: str):
        """
        Initialize the Retailer.

        Args:
            team_name: Name of the team/brewery
        """
        super().__init__(team_name, "Retailer")

        # Customer order pattern (hidden from other players)
        self.customer_orders: List[int] = []
        self.setup_customer_orders()

        # Track customer order for current week
        self.current_customer_order = 0

    def setup_customer_orders(self) -> None:
        """
        Set up the customer order pattern.

        Default pattern: 4 cases/week for weeks 1-4, then 8 cases/week
        """
        # Weeks 1-4: 4 cases per week
        self.customer_orders = [4] * 4
        # Weeks 5-50: 8 cases per week
        self.customer_orders.extend([8] * 46)

    def get_customer_order(self, week: int) -> int:
        """
        Get customer order for a specific week.

        Args:
            week: Week number (1-based)

        Returns:
            Customer order amount
        """
        if 1 <= week <= len(self.customer_orders):
            return self.customer_orders[week - 1]
        return 0

    def step_2_fill_orders(
        self, incoming_order: Optional[int] = None
    ) -> tuple[int, int]:
        """
        Step 2: Fill customer orders (not from upstream).

        For retailer, incoming orders come from customers, not upstream.

        Args:
            incoming_order: Ignored for retailer (uses customer orders)

        Returns:
            Tuple of (filled_orders, remaining_backlog)
        """
        # Get customer order for current week
        customer_order = (
            int(incoming_order)
            if incoming_order is not None
            else self.get_customer_order(self.current_week + 1)
        )
        self.current_customer_order = customer_order

        # Use parent's fill logic with customer order
        return super().step_2_fill_orders(customer_order)

    def step_5_place_order(self) -> int:
        """
        Step 5: Decide how much to order from wholesaler.

        This is the decision point. In a real game, this would be
        determined by the human player or an AI strategy.

        Returns:
            Order amount to place to wholesaler
        """
        # Simple strategy: order what the customer ordered
        # In a real game, this would be the player's decision
        return self.current_customer_order

    def execute_week(
        self, order_decision: int, customer_order: Optional[int] = None
    ) -> int:
        """
        Execute all steps for one week (retailer version).

        Args:
            order_decision: Order to place to wholesaler

        Returns:
            Amount shipped to customers this week
        """
        self.current_week += 1

        # Execute all 5 steps
        self.step_1_receive_inventory()
        filled, _ = self.step_2_fill_orders(customer_order)
        self.step_3_record(order_decision)
        outgoing_order = self.step_4_advance_order_slips()

        # Add new order to delay pipeline
        self.outgoing_order_delay.add_input(order_decision)
        self.last_order_placed = order_decision

        return filled

    def print_status(self) -> None:
        """Print current status including customer order info."""
        super().print_status()
        print(f"Customer order: {self.current_customer_order} cases")
        print("⚠️  Customer orders are CONFIDENTIAL!")

    def get_order_to_upstream(self) -> int:
        """
        Get the order that will be sent upstream (to wholesaler).

        Returns:
            Order amount from the delay pipeline
        """
        # Get the order that's exiting the delay to go to wholesaler
        slots = self.outgoing_order_delay.get_slots()
        return slots[0] if slots else 0
