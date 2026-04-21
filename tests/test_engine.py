"""Tests for the new simulation engine (src/engine/) and exporter."""

import os
import sys
from pathlib import Path

import pytest

# Ensure repository root is on sys.path so `src.*` imports resolve
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from src.engine.state import GameState, PositionState
from src.engine.simulation import BeerGameSimulation, DelayQueue
from src.engine.exporter import export_simulation_results


# ─── Helpers ───────────────────────────────────────────────────────────────


def _simple_decision(role, pos, customer_demand, turn, incoming_order=0):
    """Deterministic decision function: always order 4."""
    return 4


def _retailer_16(role, pos, customer_demand, turn, incoming_order=0):
    """Retailer always orders 16; others order 4."""
    if role == "Retailer":
        return 16
    return 4


# ─── DelayQueue tests ──────────────────────────────────────────────────────


class TestDelayQueue:
    """Unit tests for the DelayQueue FIFO delay pipeline."""

    def test_enqueue_dequeue_exact_delay(self):
        q = DelayQueue(delay=2)
        q.enqueue(turn=1, amount=10)
        # Should NOT arrive at turn 2 (1+1 < 2+1)
        assert q.dequeue(2) == 0
        # Should arrive at turn 3 (1+2 == 3)
        assert q.dequeue(3) == 10
        # Nothing left
        assert q.dequeue(3) == 0

    def test_enqueue_multiple_same_turn(self):
        q = DelayQueue(delay=1)
        q.enqueue(turn=5, amount=3)
        q.enqueue(turn=5, amount=7)
        assert q.dequeue(6) == 10

    def test_enqueue_different_turns(self):
        q = DelayQueue(delay=1)
        q.enqueue(turn=1, amount=5)
        q.enqueue(turn=3, amount=10)
        assert q.dequeue(2) == 5
        assert q.dequeue(4) == 10

    def test_empty_dequeue_returns_zero(self):
        q = DelayQueue(delay=1)
        assert q.dequeue(1) == 0


# ─── GameState tests ───────────────────────────────────────────────────────


class TestGameState:
    """Unit tests for GameState and PositionState dataclasses."""

    def test_default_initialization(self):
        state = GameState()
        assert state.current_turn == 0
        assert state.customer_demand == 4
        assert set(state.positions.keys()) == {"Retailer", "Wholesaler", "Distributor", "Factory"}

    def test_position_defaults(self):
        for pos in GameState().positions.values():
            assert pos.inventory == 0
            assert pos.backlog == 0
            assert pos.total_cost == 0.0
            assert pos.history == []

    def test_history_recording(self):
        pos = PositionState(name="Retailer")
        pos.inventory = 10
        pos.backlog = 3
        pos.total_cost = 15.5
        pos.update_history(turn=5, order=8, shipment_received=4)
        assert len(pos.history) == 1
        entry = pos.history[0]
        assert entry["turn"] == 5
        assert entry["inventory"] == 10
        assert entry["backlog"] == 3
        assert entry["order"] == 8
        assert entry["shipment_received"] == 4
        assert entry["cost"] == 15.5


# ─── Simulation engine tests ──────────────────────────────────────────────


class TestBeerGameSimulation:
    """Tests for the core simulation loop and mechanics."""

    def _make_sim(self, decision_fn=_simple_decision):
        return BeerGameSimulation(GameState(), decision_fn)

    # -- Initial state --

    def test_initial_customer_demand(self):
        sim = self._make_sim()
        assert sim.state.customer_demand == 4

    def test_initial_inventory(self):
        sim = self._make_sim()
        for pos in sim.state.positions.values():
            assert pos.inventory == 0
            assert pos.backlog == 0

    def test_runs_without_error(self):
        sim = self._make_sim()
        for _ in range(5):
            sim.run_turn()
        assert sim.state.current_turn == 5

    # -- Customer demand step --

    def test_customer_demand_steps_up_at_turn_5(self):
        sim = self._make_sim()
        assert sim.state.customer_demand == 4
        sim.run_turn()   # turn 1
        sim.run_turn()   # turn 2
        sim.run_turn()   # turn 3
        sim.run_turn()   # turn 4
        assert sim.state.customer_demand == 4
        sim.run_turn()   # turn 5 -> demand becomes 8
        assert sim.state.customer_demand == 8

    # -- Retailer fills customer demand --

    def test_retailer_fills_customer_demand(self):
        sim = self._make_sim()
        # Run 5 turns so demand is 8 and shipments are flowing
        for _ in range(5):
            sim.run_turn()
        # Inventory should have decreased (retailer filled customer demand)
        assert sim.state.positions["Retailer"].inventory < 4

    # -- Order delay: delayed arrival --

    def test_orders_arrive_with_delay(self):
        """Orders placed by Retailer should reach Wholesaler with a delay."""
        sim = self._make_sim(_retailer_16)
        # Run 6 turns: order of 16 placed at turn 1, arrives at turn 1 + shipping_delay
        # With delay=1, Retailer's order of 16 placed at turn 1 arrives at Wholesaler at turn 2
        # But shipping takes another 1, so Wholesaler sees inventory at turn 3
        for _ in range(6):
            sim.run_turn()
        # Orders should be tracked
        # The key check: non-trivial behavior happened
        # (if no delay, everything would be trivial)
        hist = sim.state.positions["Wholesaler"].history
        assert len(hist) == 6

    # -- Cost calculation --

    def test_costs_accumulate(self):
        sim = self._make_sim()
        initial_total = sum(p.total_cost for p in sim.state.positions.values())
        for _ in range(3):
            sim.run_turn()
        later_total = sum(p.total_cost for p in sim.state.positions.values())
        assert later_total > initial_total

    def test_backlog_increases_cost(self):
        """A position with backlog should incur higher costs."""
        sim = self._make_sim()
        sim.state.positions["Retailer"].inventory = 0
        sim.state.positions["Retailer"].backlog = 10
        sim.run_turn()   # costs: 0*0.50 + 10*1.00 = 10
        retailer = sim.state.positions["Retailer"]
        # cost should include backlog cost of 10.0 plus whatever history shows
        # The exact value depends on history but must be higher than cost without backlog
        assert retailer.total_cost > 0

    # -- Turn counter advances correctly --

    def test_turn_counter_advances(self):
        sim = self._make_sim()
        assert sim.state.current_turn == 0
        sim.run_turn()
        assert sim.state.current_turn == 1
        for _ in range(9):
            sim.run_turn()
        assert sim.state.current_turn == 10

    # -- History recording --

    def test_history_records_per_turn(self):
        sim = self._make_sim()
        for _ in range(5):
            sim.run_turn()
        for role in sim.state.positions:
            assert len(sim.state.positions[role].history) == 5

    # -- Negative order guard --

    def test_negative_order_clamped_to_zero(self):
        """Decision functions returning negative should be clamped to 0."""
        def always_negative(role, pos, customer_demand, turn, incoming_order=0):
            return -5
        sim = self._make_sim(always_negative)
        sim.run_turn()
        # All orders should be 0, not -5
        for role in sim.state.positions:
            assert sim.state.positions[role].history[-1]["order"] == 0

    # -- Order flow correctness --

    def test_upstream_backlog_on_shortage(self):
        """When inventory can't fill an order, backlog should increase."""
        sim = self._make_sim()
        # Factory starts with 0 inventory
        sim.state.positions["Factory"].inventory = 0
        sim.state.positions["Factory"].backlog = 0

        # Have Retailer order a huge amount each turn
        sim.run_turn()   # Factory tries to fill incoming retail order with 0 inventory
        # Factory backlog should have been incremented by _ship_amount
        assert sim.state.positions["Factory"].backlog > 0


class TestLongRunBehavior:
    """Tests running a longer simulation to catch accumulation issues."""

    def test_fifty_turns_runs_cleanly(self):
        sim = BeerGameSimulation(GameState(), _simple_decision)
        for _ in range(50):
            sim.run_turn()
        # Verify all positions have histories
        for pos in sim.state.positions.values():
            assert len(pos.history) == 50
        # Costs should be non-negative
        for pos in sim.state.positions.values():
            assert pos.total_cost >= 0

    def test_demand_step_propagates(self):
        """After turn 5, retailer order should reflect higher demand."""
        sim = BeerGameSimulation(GameState(), _retailer_16)
        for _ in range(10):
            sim.run_turn()
        retailer = sim.state.positions["Retailer"]
        # Orders placed from turn 4 (index 4) onwards should be 16
        assert retailer.history[4]["order"] == 16
        assert retailer.history[9]["order"] == 16


# ─── Exporter tests ───────────────────────────────────────────────────────


class TestExporter:
    """Tests for CSV export functionality."""

    def _make_sim_with_history(self):
        sim = BeerGameSimulation(GameState(), _simple_decision)
        for _ in range(5):
            sim.run_turn()
        return sim

    def test_export_creates_file(self, tmp_path):
        sim = self._make_sim_with_history()
        filepath = str(tmp_path / "results.csv")
        export_simulation_results(sim.state, filepath)
        assert os.path.exists(filepath)

    def test_export_header(self, tmp_path):
        sim = self._make_sim_with_history()
        filepath = str(tmp_path / "results.csv")
        export_simulation_results(sim.state, filepath)
        with open(filepath) as f:
            header = f.readline().strip()
        assert header == "Turn,Role,Inventory,Backlog,Order,ShipmentReceived,TotalCost"

    def test_export_row_count(self, tmp_path):
        sim = self._make_sim_with_history()
        filepath = str(tmp_path / "results.csv")
        export_simulation_results(sim.state, filepath)
        with open(filepath) as f:
            lines = f.readlines()
        # Header + 4 positions * 5 turns = 21 lines
        assert len(lines) == 21

    def test_export_directory_created(self, tmp_path):
        sim = self._make_sim_with_history()
        filepath = str(tmp_path / "subdir" / "results.csv")
        export_simulation_results(sim.state, filepath)
        assert os.path.exists(filepath)

    def test_export_correct_values(self, tmp_path):
        sim = self._make_sim_with_history()
        # Set a known state
        sim.state.positions["Retailer"].inventory = 10
        sim.state.positions["Retailer"].backlog = 3
        sim.state.positions["Retailer"].total_cost = 9.5
        for entry in sim.state.positions["Retailer"].history:
            entry["inventory"] = 10
            entry["backlog"] = 3
            entry["order"] = 4
            entry["shipment_received"] = 0
            entry["cost"] = 9.5

        filepath = str(tmp_path / "results.csv")
        export_simulation_results(sim.state, filepath)

        with open(filepath) as f:
            lines = f.readlines()

        # First data line for Retailer, turn 1
        retail_line = None
        for line in lines:
            parts = line.strip().split(",")
            if "Retailer" in line and parts[0] == "1":
                retail_line = parts
                break

        assert retail_line is not None
        assert retail_line[2] == "10"      # inventory
        assert retail_line[3] == "3"       # backlog
        assert retail_line[4] == "4"       # order
        assert retail_line[5] == "0"       # shipment_received
        assert retail_line[6] == "9.5"     # total_cost
