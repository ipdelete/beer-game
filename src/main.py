import argparse
import os
from src.engine.state import GameState
from src.engine.simulation import BeerGameSimulation
from src.mechanistic.agent import mechanistic_decision
from src.gabm.agent import gabm_decision
from src.engine.exporter import export_simulation_results

def main():
    parser = argparse.ArgumentParser(description="Beer Game Simulation")
    parser.add_argument("--mode", choices=["mechanistic", "gabm"], default="mechanistic", help="Simulation mode")
    parser.add_argument("--turns", type=int, default=30, help="Number of turns to run")
    parser.add_argument("--output", type=str, default=None, help="Filename to export results to (e.g. results.csv)")
    args = parser.parse_args()

    print(f"Starting Beer Game in {args.mode} mode for {args.turns} turns...")

    state = GameState(positions={}) # Initialized in __post_init__
    
    # Select decision function based on mode
    if args.mode == "mechanistic":
        decision_fn = mechanistic_decision
    elif args.mode == "gabm":
        decision_fn = gabm_decision
    else:
        print("Invalid mode selected.")
        return

    sim = BeerGameSimulation(state, decision_fn)

    for turn in range(args.turns):
        sim.run_turn()
        print(f"Turn {turn + 1}/{args.turns} completed.")

    print("\nSimulation Complete. Final Costs:")
    for role, pos in state.positions.items():
        print(f"{role}: ${pos.total_cost:.2f}")

    if args.output:
        export_simulation_results(state, args.output)
        print(f"\nResults exported to {args.output}")

if __name__ == "__main__":
    main()



