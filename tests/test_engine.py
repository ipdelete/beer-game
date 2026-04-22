"""Tests for the new Beer Game engine (Sterman-accurate orchestrator)."""

import os
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so `src.*` imports resolve.
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.engine.simulation import BeerGameEngine
from src.engine.state import PlayerView, PlayerRecord
from src.engine.exporter import export_simulation_results
from src.mechanistic.agent import mechanistic_decision, reset_state as reset_mech


# ── helpers ────────────────────────────────────────────────────────────────


def _const4(view: PlayerView) -> int:
    """Trivial decision fn: always order 4 (equilibrium)."""
    return 4


@pytest.fixture(autouse=True)
def _clean_mechanistic_state():
    """Reset Sterman smoother state between tests so they are independent."""
    reset_mech()
    yield
    reset_mech()


# ── engine: initial conditions & mechanics ─────────────────────────────────


class TestInitialConditions:
    def test_initial_inventory_is_twelve(self):
        engine = BeerGameEngine(_const4)
        assert engine.retailer.inventory == 12
        assert engine.wholesaler.inventory == 12
        assert engine.distributor.inventory == 12
        assert engine.factory.inventory == 12

    def test_initial_backlog_is_zero(self):
        engine = BeerGameEngine(_const4)
        for role in (
            engine.retailer,
            engine.wholesaler,
            engine.distributor,
            engine.factory,
        ):
            assert role.backlog == 0

    def test_week_counter_starts_zero(self):
        engine = BeerGameEngine(_const4)
        assert engine.current_week == 0


class TestWeeklyProgress:
    def test_week_counter_advances(self):
        engine = BeerGameEngine(_const4)
        engine.simulate_week()
        assert engine.current_week == 1
        engine.simulate_week()
        assert engine.current_week == 2

    def test_history_records_per_role(self):
        engine = BeerGameEngine(_const4)
        for _ in range(5):
            engine.simulate_week()
        for role in ("Retailer", "Wholesaler", "Distributor", "Factory"):
            assert len(engine.history[role]) == 5

    def test_order_history_tracks_customer(self):
        engine = BeerGameEngine(_const4)
        for _ in range(5):
            engine.simulate_week()
        # Weeks 1-4 demand is 4, week 5 jumps to 8 (classic step change).
        assert engine.order_history["Customer"] == [4, 4, 4, 4, 8]


# ── on_order accounting ────────────────────────────────────────────────────


class TestOnOrderAccounting:
    def test_wholesaler_on_order_includes_both_pipelines(self):
        """Non-Factory roles: on_order == order pipeline + shipping pipeline."""
        engine = BeerGameEngine(_const4)
        engine.simulate_week()  # Prime pipelines
        w = engine.wholesaler
        expected = (
            w.outgoing_order_delay.get_total() + w.incoming_shipping_delay.get_total()
        )
        assert engine._on_order(w) == expected

    def test_factory_on_order_is_production_only(self):
        """Factory: on_order == production pipeline only."""
        engine = BeerGameEngine(_const4)
        engine.simulate_week()
        f = engine.factory
        assert engine._on_order(f) == f.production_delay.get_total()


# ── decision fn signature & information hiding ────────────────────────────


class TestDecisionFunctionContract:
    def test_decision_fn_receives_player_view(self):
        """Decision fn is called with a PlayerView, not raw role objects."""
        seen = []

        def spy(view: PlayerView) -> int:
            seen.append(view)
            return 4

        engine = BeerGameEngine(spy)
        engine.simulate_week()
        assert len(seen) == 4
        roles = {v.role for v in seen}
        assert roles == {"Retailer", "Wholesaler", "Distributor", "Factory"}
        for v in seen:
            assert isinstance(v, PlayerView)
            assert v.week == 1

    def test_retailer_sees_customer_demand(self):
        seen = {}

        def spy(view: PlayerView) -> int:
            seen[view.role] = view
            return 4

        engine = BeerGameEngine(spy)
        engine.simulate_week()
        # Retailer's incoming_order must be the customer demand (4 at week 1).
        assert seen["Retailer"].incoming_order == 4

    def test_upstream_does_not_see_customer_demand(self):
        """Information hiding: Wholesaler's incoming_order reflects the
        retailer's *delayed* order, not the raw customer demand."""
        seen = {}

        def spy(view: PlayerView) -> int:
            seen[view.role] = view
            return 4

        engine = BeerGameEngine(spy)
        # Run enough weeks for order to traverse the 2-week delay.
        for _ in range(5):
            engine.simulate_week()
        # The Wholesaler's incoming_order is whatever emerged from the
        # retailer's outgoing_order_delay, never the raw customer demand.
        wholesaler_in = seen["Wholesaler"].incoming_order
        # Initial pipeline value is 4; with a const-4 decision, it stays 4.
        assert wholesaler_in == 4


# ── Sterman anchor-and-adjust: no bullwhip explosion ───────────────────────


class TestShermanBehaviour:
    def test_runs_without_error(self):
        engine = BeerGameEngine(mechanistic_decision)
        for _ in range(36):
            engine.simulate_week()
        assert engine.current_week == 36

    def test_no_runaway_bullwhip(self):
        """Total cost must stay bounded (well under the $500k runaway)."""
        engine = BeerGameEngine(mechanistic_decision)
        for _ in range(36):
            engine.simulate_week()
        total = sum(engine.get_total_costs().values())
        assert total < 50_000, f"Sterman strategy unexpectedly expensive: ${total}"

    def test_factory_order_peaks_are_finite(self):
        """Factory orders should peak in the low-hundreds, not the thousands."""
        engine = BeerGameEngine(mechanistic_decision)
        for _ in range(36):
            engine.simulate_week()
        factory_peak = max(engine.order_history["Factory"])
        assert factory_peak < 200

    def test_system_peaks_are_bounded(self):
        """Peaks should stay bounded (two-digit), not runaway — Sterman's
        strategy reduces but does not eliminate oscillation."""
        engine = BeerGameEngine(mechanistic_decision)
        for _ in range(36):
            engine.simulate_week()
        for role in ("Retailer", "Wholesaler", "Distributor", "Factory"):
            peak = max(engine.order_history[role])
            assert peak < 100, f"{role} peak too high: {peak}"

    def test_retailer_converges_near_demand(self):
        """Retailer is closest to the customer and should roughly track demand
        by the end of the run."""
        engine = BeerGameEngine(mechanistic_decision)
        for _ in range(36):
            engine.simulate_week()
        final_avg = sum(engine.order_history["Retailer"][-5:]) / 5
        assert abs(final_avg - 8) < 3, f"Retailer did not track demand: {final_avg}"


# ── exporter ───────────────────────────────────────────────────────────────


class TestExporter:
    def _engine_with_history(self):
        engine = BeerGameEngine(mechanistic_decision)
        for _ in range(10):
            engine.simulate_week()
        return engine

    def test_export_creates_file(self, tmp_path):
        engine = self._engine_with_history()
        path = str(tmp_path / "out.csv")
        export_simulation_results(engine, path)
        assert os.path.exists(path)

    def test_export_header_is_compatible(self, tmp_path):
        engine = self._engine_with_history()
        path = str(tmp_path / "out.csv")
        export_simulation_results(engine, path)
        with open(path) as f:
            header = f.readline().strip().split(",")
        # plot_results.py relies on Turn, Role, Order columns
        assert header[0] == "Turn"
        assert header[1] == "Role"
        assert "Order" in header

    def test_export_row_count(self, tmp_path):
        engine = self._engine_with_history()
        path = str(tmp_path / "out.csv")
        export_simulation_results(engine, path)
        with open(path) as f:
            lines = f.readlines()
        # header + 4 roles * 10 weeks
        assert len(lines) == 1 + 4 * 10

    def test_export_subdir_created(self, tmp_path):
        engine = self._engine_with_history()
        path = str(tmp_path / "sub" / "out.csv")
        export_simulation_results(engine, path)
        assert os.path.exists(path)


# ── two-phase week: decisions see the same snapshot ───────────────────────


class TestTwoPhaseWeek:
    def test_all_decisions_fire_before_any_execution(self):
        """All four decision callbacks must fire before any role's execute_week."""
        events = []

        def dec(view: PlayerView) -> int:
            events.append(("decide", view.role, view.week))
            return 4

        engine = BeerGameEngine(dec)
        # Patch execute_week on each role to log order.
        orig = {
            "Retailer": engine.retailer.execute_week,
            "Wholesaler": engine.wholesaler.execute_week,
            "Distributor": engine.distributor.execute_week,
            "Factory": engine.factory.execute_week,
        }

        def wrap(name, fn):
            def inner(*a, **kw):
                events.append(("execute", name))
                return fn(*a, **kw)

            return inner

        engine.retailer.execute_week = wrap("Retailer", orig["Retailer"])
        engine.wholesaler.execute_week = wrap("Wholesaler", orig["Wholesaler"])
        engine.distributor.execute_week = wrap("Distributor", orig["Distributor"])
        engine.factory.execute_week = wrap("Factory", orig["Factory"])

        engine.simulate_week()
        decide_events = [e for e in events if e[0] == "decide"]
        execute_events = [e for e in events if e[0] == "execute"]
        # All 4 decisions before any execution
        last_decide_idx = events.index(decide_events[-1])
        first_execute_idx = events.index(execute_events[0])
        assert last_decide_idx < first_execute_idx
