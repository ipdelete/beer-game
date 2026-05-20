"""Pytest fixtures for Beer Game simulation tests."""

import pytest
import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import with importlib due to hyphen in filename
import importlib.util

spec = importlib.util.spec_from_file_location("full_demo", src_path / "full-demo.py")
full_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(full_demo)

BeerGameSimulation = full_demo.BeerGameSimulation


@pytest.fixture
def fresh_simulation():
    """Create a fresh simulation instance for testing."""
    return BeerGameSimulation("Test Brewery")


@pytest.fixture
def simulation_after_1_week(fresh_simulation):
    """Simulation after running 1 week."""
    sim = fresh_simulation
    sim.simulate_week()
    return sim


@pytest.fixture
def simulation_after_5_weeks(fresh_simulation):
    """Simulation after running 5 weeks."""
    sim = fresh_simulation
    for _ in range(5):
        sim.simulate_week()
    return sim


@pytest.fixture
def simulation_after_10_weeks(fresh_simulation):
    """Simulation after running 10 weeks."""
    sim = fresh_simulation
    for _ in range(10):
        sim.simulate_week()
    return sim


@pytest.fixture
def simulation_after_15_weeks(fresh_simulation):
    """Simulation after running 15 weeks."""
    sim = fresh_simulation
    for _ in range(15):
        sim.simulate_week()
    return sim


@pytest.fixture
def simulation_after_20_weeks(fresh_simulation):
    """Simulation after running 20 weeks."""
    sim = fresh_simulation
    for _ in range(20):
        sim.simulate_week()
    return sim


@pytest.fixture
def simulation_after_25_weeks(fresh_simulation):
    """Simulation after running 25 weeks."""
    sim = fresh_simulation
    for _ in range(25):
        sim.simulate_week()
    return sim


@pytest.fixture
def simulation_after_30_weeks(fresh_simulation):
    """Simulation after running 30 weeks."""
    sim = fresh_simulation
    for _ in range(30):
        sim.simulate_week()
    return sim


@pytest.fixture
def full_simulation(fresh_simulation):
    """Complete 36-week simulation for full analysis."""
    sim = fresh_simulation
    for _ in range(36):
        sim.simulate_week()
    return sim


@pytest.fixture
def expected_week_snapshots():
    """Expected values at key weeks from the classic 36-week simulation."""
    return {
        1: {
            "customer_order": 4,
            "positions": {
                "Retailer": {"inventory": 12, "backlog": 0, "cost": 6.00, "order": 4},
                "Wholesaler": {"inventory": 12, "backlog": 0, "cost": 6.00, "order": 4},
                "Distributor": {
                    "inventory": 12,
                    "backlog": 0,
                    "cost": 6.00,
                    "order": 4,
                },
                "Factory": {"inventory": 12, "backlog": 0, "cost": 6.00, "order": 4},
            },
        },
        5: {
            "customer_order": 8,
            "positions": {
                "Retailer": {"inventory": 4, "backlog": 0, "cost": 2.00, "order": 8},
                "Wholesaler": {"inventory": 12, "backlog": 0, "cost": 6.00, "order": 4},
                "Distributor": {
                    "inventory": 12,
                    "backlog": 0,
                    "cost": 6.00,
                    "order": 4,
                },
                "Factory": {"inventory": 12, "backlog": 0, "cost": 6.00, "order": 4},
            },
        },
        10: {
            "customer_order": 8,
            "positions": {
                "Retailer": {"inventory": 0, "backlog": 8, "cost": 8.00, "order": 16},
                "Wholesaler": {
                    "inventory": 0,
                    "backlog": 14,
                    "cost": 14.00,
                    "order": 20,
                },
                "Distributor": {"inventory": 4, "backlog": 0, "cost": 2.00, "order": 8},
                "Factory": {"inventory": 12, "backlog": 0, "cost": 6.00, "order": 4},
            },
        },
        15: {
            "customer_order": 8,
            "positions": {
                "Retailer": {"inventory": 0, "backlog": 12, "cost": 12.00, "order": 18},
                "Wholesaler": {
                    "inventory": 0,
                    "backlog": 60,
                    "cost": 60.00,
                    "order": 47,
                },
                "Distributor": {
                    "inventory": 0,
                    "backlog": 85,
                    "cost": 85.00,
                    "order": 70,
                },
                "Factory": {"inventory": 0, "backlog": 47, "cost": 47.00, "order": 54},
            },
        },
        20: {
            "customer_order": 8,
            "positions": {
                "Retailer": {"inventory": 0, "backlog": 12, "cost": 12.00, "order": 18},
                "Wholesaler": {
                    "inventory": 0,
                    "backlog": 84,
                    "cost": 84.00,
                    "order": 71,
                },
                "Distributor": {
                    "inventory": 0,
                    "backlog": 155,
                    "cost": 155.00,
                    "order": 152,
                },
                "Factory": {"inventory": 0, "backlog": 90, "cost": 90.00, "order": 180},
            },
        },
        25: {
            "customer_order": 8,
            "positions": {
                "Retailer": {"inventory": 130, "backlog": 0, "cost": 65.00, "order": 8},
                "Wholesaler": {
                    "inventory": 330,
                    "backlog": 0,
                    "cost": 165.00,
                    "order": 8,
                },
                "Distributor": {
                    "inventory": 351,
                    "backlog": 0,
                    "cost": 175.50,
                    "order": 18,
                },
                "Factory": {"inventory": 142, "backlog": 0, "cost": 71.00, "order": 96},
            },
        },
        30: {
            "customer_order": 8,
            "positions": {
                "Retailer": {"inventory": 138, "backlog": 0, "cost": 69.00, "order": 8},
                "Wholesaler": {
                    "inventory": 387,
                    "backlog": 0,
                    "cost": 193.50,
                    "order": 8,
                },
                "Distributor": {
                    "inventory": 614,
                    "backlog": 0,
                    "cost": 307.00,
                    "order": 8,
                },
                "Factory": {"inventory": 358, "backlog": 0, "cost": 179.00, "order": 8},
            },
        },
        36: {
            "customer_order": 8,
            "positions": {
                "Retailer": {"inventory": 138, "backlog": 0, "cost": 69.00, "order": 8},
                "Wholesaler": {
                    "inventory": 387,
                    "backlog": 0,
                    "cost": 193.50,
                    "order": 8,
                },
                "Distributor": {
                    "inventory": 614,
                    "backlog": 0,
                    "cost": 307.00,
                    "order": 8,
                },
                "Factory": {"inventory": 358, "backlog": 0, "cost": 179.00, "order": 8},
            },
        },
    }


@pytest.fixture
def expected_order_amplification():
    """Expected order amplification from the classic 36-week simulation."""
    return {
        "Customer": {"min": 4, "max": 8, "avg": 7.6, "amplification": 1.0},
        "Retailer": {"min": 4, "max": 20, "avg": 11.6, "amplification": 4.0},
        "Wholesaler": {"min": 4, "max": 71, "avg": 22.2, "amplification": 16.8},
        "Distributor": {"min": 4, "max": 152, "avg": 39.2, "amplification": 37.0},
        "Factory": {"min": 4, "max": 196, "avg": 48.8, "amplification": 48.0},
    }


@pytest.fixture
def expected_total_costs():
    """Expected total costs from the classic 36-week simulation."""
    return {
        "Retailer": 1109.00,
        "Wholesaler": 3169.00,
        "Distributor": 4745.00,
        "Factory": 2663.50,
        "Total": 11686.50,
    }
