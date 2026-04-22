"""CSV exporter for Beer Game engine history.

Writes one row per (week, role) with columns matching the original format so
`scripts/plot_results.py` continues to work.
"""

import csv
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .simulation import BeerGameEngine


def export_simulation_results(engine: "BeerGameEngine", filename: str) -> None:
    dirname = os.path.dirname(filename)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Turn",
                "Role",
                "Inventory",
                "Backlog",
                "Order",
                "ShipmentReceived",
                "TotalCost",
                "IncomingOrder",
                "OnOrder",
            ]
        )
        # Emit rows in role-major, week-minor order so legacy consumers still
        # see the same grouping.
        running_cost = {name: 0.0 for name in engine.history}
        for role_name, records in engine.history.items():
            running_cost[role_name] = 0.0
            for rec in records:
                running_cost[role_name] += rec.cost
                writer.writerow(
                    [
                        rec.week,
                        role_name,
                        rec.inventory,
                        rec.backlog,
                        rec.order_placed,
                        rec.shipment_received,
                        round(running_cost[role_name], 2),
                        rec.incoming_order,
                        rec.on_order,
                    ]
                )
