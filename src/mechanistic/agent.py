from ..engine.state import PositionState

def mechanistic_decision(role: str, pos: PositionState, customer_demand: int, turn: int = 0) -> int:
    """
    Simple rule-based logic for the Beer Game.
    Strategy: Try to keep inventory equal to demand and cover backlog.
    """
    # Target inventory based on current perceived demand
    # (In a real game, the agent doesn't know the customer demand unless they are the Retailer)
    target_inventory = customer_demand if role == 'Retailer' else 4 # Default assumption
    
    # If not retailer, they don't know the exact demand, but they see their own backlog
    # A common mechanistic strategy is: Order = (Target Inventory - Current Inventory) + Backlog
    
    order = (target_inventory - pos.inventory) + pos.backlog
    
    return max(0, int(order))
