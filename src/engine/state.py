from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class PositionState:
    name: str
    inventory: int = 0
    backlog: int = 0
    incoming_shipments: List[Dict] = field(default_factory=list) # List of {'arrival_turn': int, 'amount': int}
    total_cost: float = 0.0
    history: List[Dict] = field(default_factory=list)

    def update_history(self, turn: int, order: int, shipment_received: int):
        self.history.append({
            'turn': turn,
            'inventory': self.inventory,
            'backlog': self.backlog,
            'order': order,
            'shipment_received': shipment_received,
            'cost': self.total_cost
        })

@dataclass
class GameState:
    positions: Dict[str, PositionState]
    current_turn: int = 0
    customer_demand: int = 4
    
    def __post_init__(self):
        # Initialize the 4 standard roles
        roles = ['Retailer', 'Wholesaler', 'Distributor', 'Factory']
        self.positions = {role: PositionState(name=role) for role in roles}
