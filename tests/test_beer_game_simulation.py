"""Core tests for Beer Game simulation functionality."""

import pytest


class TestInitialConditions:
    """Test the initial setup of the Beer Game simulation."""

    def test_initial_inventory(self, fresh_simulation):
        """All positions start with 12 cases inventory."""
        sim = fresh_simulation
        assert sim.retailer.inventory == 12
        assert sim.wholesaler.inventory == 12
        assert sim.distributor.inventory == 12
        assert sim.factory.inventory == 12

    def test_initial_backlog(self, fresh_simulation):
        """All positions start with 0 backlog."""
        sim = fresh_simulation
        assert sim.retailer.backlog == 0
        assert sim.wholesaler.backlog == 0
        assert sim.distributor.backlog == 0
        assert sim.factory.backlog == 0

    def test_initial_week(self, fresh_simulation):
        """Simulation starts at week 0."""
        sim = fresh_simulation
        assert sim.current_week == 0

    def test_team_name_assignment(self, fresh_simulation):
        """All roles get the correct team name."""
        sim = fresh_simulation
        assert sim.retailer.team_name == "Test Brewery"
        assert sim.wholesaler.team_name == "Test Brewery"
        assert sim.distributor.team_name == "Test Brewery"
        assert sim.factory.team_name == "Test Brewery"


class TestCustomerDemandPattern:
    """Test the customer demand pattern (4 cases weeks 1-4, then 8 cases)."""

    def test_week_1_demand(self, simulation_after_1_week):
        """Customer orders 4 cases in week 1."""
        sim = simulation_after_1_week
        customer_order = sim.retailer.get_customer_order(1)
        assert customer_order == 4

    def test_weeks_1_to_4_demand(self, fresh_simulation):
        """Customer orders 4 cases in weeks 1-4."""
        sim = fresh_simulation
        for week in range(1, 5):
            customer_order = sim.retailer.get_customer_order(week)
            assert customer_order == 4, f"Week {week} should have 4 cases demand"

    def test_week_5_and_beyond_demand(self, fresh_simulation):
        """Customer orders 8 cases from week 5 onwards."""
        sim = fresh_simulation
        for week in range(5, 37):
            customer_order = sim.retailer.get_customer_order(week)
            assert customer_order == 8, f"Week {week} should have 8 cases demand"


class TestWeeklySimulationProgress:
    """Test that simulation progresses correctly week by week."""

    def test_week_counter_advances(self, fresh_simulation):
        """Week counter advances correctly."""
        sim = fresh_simulation
        assert sim.current_week == 0

        sim.simulate_week()
        assert sim.current_week == 1

        sim.simulate_week()
        assert sim.current_week == 2

    def test_order_history_tracking(self, simulation_after_5_weeks):
        """Order history is tracked for all positions."""
        sim = simulation_after_5_weeks

        assert len(sim.order_history["Customer"]) == 5
        assert len(sim.order_history["Retailer"]) == 5
        assert len(sim.order_history["Wholesaler"]) == 5
        assert len(sim.order_history["Distributor"]) == 5
        assert len(sim.order_history["Factory"]) == 5

        # Check first 4 weeks have customer demand of 4
        for i in range(4):
            assert sim.order_history["Customer"][i] == 4

        # Check week 5 has customer demand of 8
        assert sim.order_history["Customer"][4] == 8


class TestCostCalculations:
    """Test cost calculations for inventory and backlog."""

    def test_inventory_cost_calculation(self, fresh_simulation):
        """Inventory costs $0.50 per case per week."""
        sim = fresh_simulation
        # Each position starts with 12 cases inventory = $6.00 cost
        assert sim.retailer.get_current_cost() == 6.00
        assert sim.wholesaler.get_current_cost() == 6.00
        assert sim.distributor.get_current_cost() == 6.00
        assert sim.factory.get_current_cost() == 6.00

    def test_backlog_cost_calculation(self, fresh_simulation):
        """Backlog costs $1.00 per case per week."""
        sim = fresh_simulation

        # Manually set backlog for testing
        sim.retailer.backlog = 10
        sim.retailer.inventory = 0

        expected_cost = 10 * 1.00  # 10 cases backlog at $1.00 each
        assert sim.retailer.get_current_cost() == expected_cost

    def test_mixed_inventory_backlog_cost(self, fresh_simulation):
        """Cost calculation with both inventory and backlog."""
        sim = fresh_simulation

        # Set up mixed scenario
        sim.retailer.inventory = 5
        sim.retailer.backlog = 3

        expected_cost = (5 * 0.50) + (3 * 1.00)  # $2.50 + $3.00 = $5.50
        assert sim.retailer.get_current_cost() == 5.50


class TestSpecificWeekSnapshots:
    """Test specific week snapshots against classic 36-week simulation values."""

    def test_week_1_snapshot(self, simulation_after_1_week, expected_week_snapshots):
        """Validate week 1 matches expected values."""
        sim = simulation_after_1_week
        expected = expected_week_snapshots[1]

        # Check customer order
        customer_order = sim.retailer.get_customer_order(1)
        assert customer_order == expected["customer_order"]

        # Check each position
        positions = [
            (sim.retailer, "Retailer"),
            (sim.wholesaler, "Wholesaler"),
            (sim.distributor, "Distributor"),
            (sim.factory, "Factory"),
        ]

        for role, name in positions:
            exp_pos = expected["positions"][name]
            assert role.inventory == exp_pos["inventory"], f"{name} inventory mismatch"
            assert role.backlog == exp_pos["backlog"], f"{name} backlog mismatch"
            assert (
                abs(role.get_current_cost() - exp_pos["cost"]) < 0.01
            ), f"{name} cost mismatch"

    def test_week_5_snapshot(self, simulation_after_5_weeks, expected_week_snapshots):
        """Validate week 5 matches expected values."""
        sim = simulation_after_5_weeks
        expected = expected_week_snapshots[5]

        # Check customer order (should be 8 starting week 5)
        customer_order = sim.retailer.get_customer_order(5)
        assert customer_order == expected["customer_order"]

        # Check retailer shows effect of demand change
        assert sim.retailer.inventory == expected["positions"]["Retailer"]["inventory"]
        assert sim.retailer.backlog == expected["positions"]["Retailer"]["backlog"]
        assert (
            abs(
                sim.retailer.get_current_cost()
                - expected["positions"]["Retailer"]["cost"]
            )
            < 0.01
        )

    def test_week_10_backlog_buildup(
        self, simulation_after_10_weeks, expected_week_snapshots
    ):
        """Validate week 10 shows backlog building up downstream."""
        sim = simulation_after_10_weeks
        expected = expected_week_snapshots[10]

        # Retailer should have backlog by week 10
        retailer_exp = expected["positions"]["Retailer"]
        assert sim.retailer.inventory == retailer_exp["inventory"]
        assert sim.retailer.backlog == retailer_exp["backlog"]

        # Wholesaler should also have backlog
        wholesaler_exp = expected["positions"]["Wholesaler"]
        assert sim.wholesaler.inventory == wholesaler_exp["inventory"]
        assert sim.wholesaler.backlog == wholesaler_exp["backlog"]

    def test_week_25_surplus_swing(
        self, simulation_after_25_weeks, expected_week_snapshots
    ):
        """Validate week 25 shows swing to high inventory."""
        sim = simulation_after_25_weeks
        expected = expected_week_snapshots[25]

        # All positions should have high inventory, no backlog
        positions = [
            (sim.retailer, "Retailer"),
            (sim.wholesaler, "Wholesaler"),
            (sim.distributor, "Distributor"),
            (sim.factory, "Factory"),
        ]

        for role, name in positions:
            exp_pos = expected["positions"][name]
            assert role.backlog == 0, f"{name} should have no backlog in week 25"
            assert role.inventory > 100, f"{name} should have high inventory in week 25"

    def test_week_36_final_state(self, full_simulation, expected_week_snapshots):
        """Validate final week 36 state."""
        sim = full_simulation
        expected = expected_week_snapshots[36]

        # Check final inventory levels are stable and high
        positions = [
            (sim.retailer, "Retailer"),
            (sim.wholesaler, "Wholesaler"),
            (sim.distributor, "Distributor"),
            (sim.factory, "Factory"),
        ]

        for role, name in positions:
            exp_pos = expected["positions"][name]
            assert (
                role.backlog == exp_pos["backlog"]
            ), f"{name} backlog mismatch in week 36"
            assert (
                role.inventory == exp_pos["inventory"]
            ), f"{name} inventory mismatch in week 36"


class TestTotalCostAccumulation:
    """Test total cost accumulation over the full simulation."""

    def test_cost_accumulation_over_time(self, fresh_simulation):
        """Total costs increase as simulation progresses."""
        sim = fresh_simulation

        # Run a few weeks and check costs increase
        initial_retailer_cost = sim.retailer.get_total_cost()

        for _ in range(5):
            sim.simulate_week()

        later_retailer_cost = sim.retailer.get_total_cost()
        assert later_retailer_cost > initial_retailer_cost

    def test_final_total_costs(self, full_simulation, expected_total_costs):
        """Final total costs match expected classic simulation values."""
        sim = full_simulation
        expected = expected_total_costs

        # Test individual role costs (with some tolerance for floating point)
        assert abs(sim.retailer.get_total_cost() - expected["Retailer"]) < 1.0
        assert abs(sim.wholesaler.get_total_cost() - expected["Wholesaler"]) < 1.0
        assert abs(sim.distributor.get_total_cost() - expected["Distributor"]) < 1.0
        assert abs(sim.factory.get_total_cost() - expected["Factory"]) < 1.0

        # Test total system cost
        total_cost = (
            sim.retailer.get_total_cost()
            + sim.wholesaler.get_total_cost()
            + sim.distributor.get_total_cost()
            + sim.factory.get_total_cost()
        )

        assert abs(total_cost - expected["Total"]) < 5.0  # Allow some tolerance
