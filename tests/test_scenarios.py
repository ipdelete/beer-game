import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.scenarios import filter_scenarios, load_scenarios, parse_release


def test_parse_release_orders_quarters():
    assert parse_release("2026-Q1") < parse_release("2026-Q2")
    assert parse_release("2026-Q4") < parse_release("2027-Q1")


def test_parse_release_rejects_invalid_format():
    for value in ("2026-q1", "2026-Q5", "26-Q1"):
        try:
            parse_release(value)
        except ValueError as exc:
            assert value in str(exc)
        else:
            raise AssertionError("expected invalid release")


def test_filter_scenarios_release_and_removal_boundaries():
    scenarios = [
        _scenario("released-before", "2026-Q1", None),
        _scenario("released-at", "2026-Q2", None),
        _scenario("future", "2026-Q3", None),
        _scenario("removed-at", "2026-Q1", "2026-Q2"),
        _scenario("removed-after", "2026-Q1", "2026-Q3"),
    ]

    active_release, filtered = filter_scenarios(scenarios, "2026-Q2")

    assert active_release == "2026-Q2"
    assert [scenario["scenario_id"] for scenario in filtered] == [
        "released-before",
        "released-at",
        "removed-after",
    ]


def test_filter_scenarios_defaults_to_latest_release():
    active_release, filtered = filter_scenarios(
        [
            _scenario("old", "2026-Q1", None),
            _scenario("new", "2026-Q3", None),
        ]
    )

    assert active_release == "2026-Q3"
    assert [scenario["scenario_id"] for scenario in filtered] == ["old", "new"]


def test_filter_scenarios_rejects_missing_release_date():
    scenario = _scenario("missing", "2026-Q1", None)
    scenario.pop("release_date")

    try:
        filter_scenarios([scenario], "2026-Q2")
    except ValueError as exc:
        assert "release_date" in str(exc)
    else:
        raise AssertionError("expected missing release date error")


def test_filter_scenarios_rejects_empty_result():
    try:
        filter_scenarios([_scenario("future", "2027-Q1", None)], "2026-Q2")
    except ValueError as exc:
        assert "No scenarios active for release 2026-Q2" in str(exc)
    else:
        raise AssertionError("expected empty filtered scenarios error")


def test_load_scenarios_reads_yaml_and_filters(tmp_path):
    active = tmp_path / "active.yaml"
    future = tmp_path / "future.yaml"
    active.write_text(_scenario_yaml("active", "2026-Q1", None))
    future.write_text(_scenario_yaml("future", "2026-Q3", None))

    scenarios = load_scenarios([active, future], "2026-Q2")

    assert [scenario["scenario_id"] for scenario in scenarios] == ["active"]


def _scenario(scenario_id: str, release_date: str, removal_date: str | None) -> dict:
    return {
        "scenario_id": scenario_id,
        "demand_pattern": "step",
        "params": {"low": 4, "high": 8, "step_week": 5},
        "weeks": 1,
        "costs": {"holding": 0.5, "backlog": 1.0},
        "scenario_seed": 42,
        "release_date": release_date,
        "removal_date": removal_date,
    }


def _scenario_yaml(
    scenario_id: str, release_date: str, removal_date: str | None
) -> str:
    removal = "null" if removal_date is None else f'"{removal_date}"'
    return f"""
scenario_id: {scenario_id}
demand_pattern: step
params: {{low: 4, high: 8, step_week: 5}}
weeks: 1
costs: {{holding: 0.5, backlog: 1.0}}
scenario_seed: 42
release_date: "{release_date}"
removal_date: {removal}
"""
