from ..engine.state import PositionState


def mechanistic_decision(
    role: str,
    pos: PositionState,
    customer_demand: int,
    turn: int = 0,
    incoming_order: int = 0,
) -> int:
    """
    Simple rule-based logic for the Beer Game.
    Strategy: Try to keep inventory equal to demand and cover backlog.
    """
    # Target inventory based on current perceived demand.
    # Retailer sees customer demand directly; upstream roles use the most recent
    # incoming order from their downstream partner as a demand proxy. Fall back
    # to 4 (the equilibrium order) if no incoming order is available yet.
    if role == "Retailer":
        target_inventory = customer_demand
    else:
        target_inventory = incoming_order if incoming_order > 0 else 4

    # Order = (Target Inventory - Current Inventory) + Backlog
    order = (target_inventory - pos.inventory) + pos.backlog

    return max(0, int(order))
