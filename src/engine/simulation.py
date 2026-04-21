from typing import List, Dict, Callable
from .state import GameState, PositionState

class BeerGameSimulation:
    def __init__(self, state: GameState, decision_fn: Callable[[str, PositionState, int], int]):
        self.state = state
        self.decision_fn = decision_fn # (role_name, current_state, customer_demand) -> order_amount
        self.shipping_delay = 2 # Standard Beer Game delay
        
    def run_turn(self):
        self.state.current_turn += 1
        turn = self.state.current_turn
        
        # 1. Update Customer Demand
        if turn == 5: # Traditional step increase
            self.state.customer_demand = 8
            
        # 2. Process Shipments & Demand for each position
        # We iterate backwards from Factory to Retailer to ensure shipment flow logic
        roles = ['Factory', 'Distributor', 'Wholesaler', 'Retailer']
        
        # Temp storage for orders placed this turn to be shipped next
        current_orders = {}

        for role in roles:
            pos = self.state.positions[role]
            
            # A. Receive shipments arriving this turn
            shipment_received = 0
            for shipment in pos.incoming_shipments[:]:
                if shipment['arrival_turn'] == turn:
                    shipment_received += shipment['amount']
                    pos.incoming_shipments.remove(shipment)
            
            pos.inventory += shipment_received
            
            # B. Calculate Demand
            if role == 'Retailer':
                demand = self.state.customer_demand
            else:
                # Demand for this position is the orders from the downstream position
                # For simplification in this loop, we'll look at the previous turn's orders from downstream
                # But the game actually works where Retailer orders from Wholesaler, etc.
                # We'll handle the order flow in Step C.
                demand = 0 # Handled by agent logic usually, but the engine must apply it.
            
            # C. Get Order from Agent
            # In the classic game, an agent sees their inventory/backlog and decides what to order
            # Pass the current turn to allow the agent to track time
            order = self.decision_fn(role, pos, self.state.customer_demand if role == 'Retailer' else 0, turn)
            current_orders[role] = order
            
            # D. Process Demand (Retailer specific for now, others handled by order flow)
            if role == 'Retailer':
                pos.inventory -= demand
                if pos.inventory < 0:
                    pos.backlog += abs(pos.inventory)
                    pos.inventory = 0
            
            # E. Calculate Costs
            pos.total_cost += (pos.inventory * 0.50) + (pos.backlog * 1.00)
            
            pos.update_history(turn, order, shipment_received)

        # 3. Handle Order Flow (Shipments)
        # Retailer -> Wholesaler -> Distributor -> Factory
        flow = [('Retailer', 'Wholesaler'), ('Wholesaler', 'Distributor'), ('Distributor', 'Factory')]
        
        for downstream, upstream in flow:
            order_amount = current_orders[downstream]
            upstream_pos = self.state.positions[upstream]
            
            # Upstream ships what they have, or what they can
            # In the classic game, the upstream agent fulfills the order from inventory
            # and puts the rest in backlog.
            
            # To keep it simple for the engine:
            # 1. Upstream subtracts from inventory
            # 2. Create a shipment that arrives in shipping_delay turns
            
            shipment_amount = 0
            if upstream_pos.inventory >= order_amount:
                shipment_amount = order_amount
                upstream_pos.inventory -= order_amount
            else:
                shipment_amount = upstream_pos.inventory
                upstream_pos.inventory = 0
                # Note: Backlog for upstream is handled when they receive orders they cannot fill
                # But the rules vary. Standard: if you can't fill, it's backlog.
                upstream_pos.backlog += (order_amount - shipment_amount)
            
            # Add shipment to downstream's queue
            downstream_pos = self.state.positions[downstream]
            downstream_pos.incoming_shipments.append({
                'arrival_turn': turn + self.shipping_delay,
                'amount': shipment_amount
            })

        return current_orders
