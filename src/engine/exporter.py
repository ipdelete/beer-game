import csv
import os
from typing import Dict
from .state import GameState


def export_simulation_results(state: GameState, filename: str):
    """
    Exports the simulation history of all positions to a CSV file.
    Format: Turn, Role, Inventory, Backlog, Order, ShipmentReceived, TotalCost
    """
    # Ensure directory exists
    dirname = os.path.dirname(filename)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(
            [
                "Turn",
                "Role",
                "Inventory",
                "Backlog",
                "Order",
                "ShipmentReceived",
                "TotalCost",
            ]
        )

        for role, pos in state.positions.items():
            for entry in pos.history:
                writer.writerow(
                    [
                        entry["turn"],
                        role,
                        entry["inventory"],
                        entry["backlog"],
                        entry["order"],
                        entry["shipment_received"],
                        entry["cost"],
                    ]
                )
