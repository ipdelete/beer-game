"""Beer Game CLI entry point.

Runs the Sterman-accurate simulation under either the mechanistic (anchor-and-
adjust) decision rule or the GABM (LLM-backed) decision rule and optionally
exports the per-week history to CSV for `scripts/plot_results.py`.
"""

import argparse

from src.engine.simulation import BeerGameEngine
from src.engine.exporter import export_simulation_results
from src.mechanistic.agent import mechanistic_decision, reset_state as reset_mech
from src.gabm.agent import gabm_decision, reset_state as reset_gabm


def main() -> None:
    parser = argparse.ArgumentParser(description="Beer Game Simulation")
    parser.add_argument(
        "--mode",
        choices=["mechanistic", "gabm"],
        default="mechanistic",
        help="Decision strategy",
    )
    parser.add_argument(
        "--turns", type=int, default=36, help="Number of weeks to simulate"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Filename to export per-week results to (e.g. results.csv)",
    )
    args = parser.parse_args()

    print(f"Starting Beer Game in {args.mode} mode for {args.turns} weeks...")

    if args.mode == "mechanistic":
        reset_mech()
        decision_fn = mechanistic_decision
    else:
        reset_gabm()
        decision_fn = gabm_decision

    engine = BeerGameEngine(decision_fn=decision_fn)

    for week in range(args.turns):
        engine.simulate_week()
        print(f"Week {week + 1}/{args.turns} completed.")

    print("\nSimulation Complete. Final Costs:")
    for role, cost in engine.get_total_costs().items():
        print(f"  {role}: ${cost:.2f}")

    if args.output:
        export_simulation_results(engine, args.output)
        print(f"\nResults exported to {args.output}")


if __name__ == "__main__":
    main()
