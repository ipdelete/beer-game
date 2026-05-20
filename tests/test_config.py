import json
import sys
from pathlib import Path

from click.testing import CliRunner

repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.bench.cli.main import bench
from src.bench.config import deep_merge, load_config, resolved_config_hash


def test_load_config_resolves_nested_imports():
    cfg = load_config("configs/runs/smoke.yaml")

    assert cfg["schema_version"] == "1.0.0"
    assert cfg["weeks"] == 1
    assert cfg["epochs"] == 1
    assert cfg["models"] == [
        {
            "id": "mechanistic",
            "provider": "mechanistic",
            "model": "mechanistic",
        }
    ]
    assert cfg["scenarios"][0]["scenario_id"] == "step_4_8_1w"
    assert cfg["scenarios"][0]["params"]["step_week"] == 5
    assert "_list_policy" not in cfg


def test_deep_merge_concatenates_lists_by_default():
    assert deep_merge({"models": ["a"]}, {"models": ["b"]}) == {"models": ["a", "b"]}


def test_deep_merge_replaces_lists_with_policy():
    assert deep_merge(
        {"models": ["a"]},
        {"_list_policy": {"models": "replace"}, "models": ["b"]},
    ) == {"models": ["b"]}


def test_load_config_default_and_overwrite(tmp_path):
    path = tmp_path / "run.yaml"
    path.write_text("""
schema_version: "1.0.0"
active_release: "2026-Q2"
run_seed: 1
weeks: 1
epochs: 1
mode: mechanistic
default:
  runner:
    parallel: 1
    persist_traces: false
runner:
  parallel: 2
overwrite:
  cache:
    enabled: false
scenarios:
  - import: "scenario.yaml"
models:
  - import: "model.yaml"
telemetry:
  otlp_endpoint: null
""")
    (tmp_path / "model.yaml").write_text(
        "id: mechanistic\nprovider: mechanistic\nmodel: mechanistic\n"
    )
    (tmp_path / "scenario.yaml").write_text("""
scenario_id: s
demand_pattern: step
params: {low: 4, high: 8, step_week: 5}
weeks: 1
costs: {holding: 0.5, backlog: 1.0}
scenario_seed: 42
release_date: "2026-Q1"
removal_date: null
""")

    cfg = load_config(path)

    assert cfg["runner"]["parallel"] == 2
    assert cfg["runner"]["persist_traces"] is False
    assert cfg["cache"]["enabled"] is False


def test_load_config_detects_cycles(tmp_path):
    (tmp_path / "a.yaml").write_text('import: "b.yaml"\n')
    (tmp_path / "b.yaml").write_text('import: "a.yaml"\n')

    try:
        load_config(tmp_path / "a.yaml")
    except ValueError as exc:
        assert "cycle" in str(exc)
        assert "a.yaml" in str(exc)
        assert "b.yaml" in str(exc)
    else:
        raise AssertionError("expected cycle error")


def test_load_config_rejects_secret_like_keys(tmp_path):
    path = tmp_path / "secret.yaml"
    path.write_text("""
schema_version: "1.0.0"
active_release: "2026-Q2"
run_seed: 1
weeks: 1
epochs: 1
mode: mechanistic
models:
  - id: bad
    provider: openai-compatible
    api_key: nope
scenarios: []
""")

    try:
        load_config(path)
    except ValueError as exc:
        assert "api_key" in str(exc)
    else:
        raise AssertionError("expected secret key error")


def test_load_config_validation_error_mentions_file_and_key(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("schema_version: 1\nweeks: 0\n")

    try:
        load_config(path)
    except ValueError as exc:
        assert str(path) in str(exc)
        assert "weeks" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_resolved_config_hash_is_stable_for_equivalent_configs(tmp_path):
    inline = load_config("configs/runs/smoke.yaml")
    path = tmp_path / "inline.yaml"
    path.write_text("""
schema_version: "1.0.0"
active_release: "2026-Q2"
run_seed: 12345
weeks: 1
epochs: 1
mode: mechanistic
runner: {parallel: 1, persist_traces: false}
cache: {enabled: true}
scenarios:
  - scenario_id: step_4_8_1w
    demand_pattern: step
    params: {low: 4, high: 8, step_week: 5}
    weeks: 1
    costs: {holding: 0.5, backlog: 1.0}
    scenario_seed: 42
    release_date: "2026-Q1"
    removal_date: null
models:
  - id: mechanistic
    provider: mechanistic
    model: mechanistic
telemetry: {otlp_endpoint: null}
""")
    explicit = load_config(path)

    assert inline == explicit
    assert resolved_config_hash(inline) == resolved_config_hash(explicit)


def test_bench_run_config_writes_resolved_manifest(tmp_path):
    result = CliRunner().invoke(
        bench,
        [
            "run",
            "--config",
            "configs/runs/smoke.yaml",
            "--runs-dir",
            str(tmp_path),
            "--run-id",
            "config-smoke",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads(
        (tmp_path / "config-smoke.eval" / "manifest.json").read_text()
    )
    cfg = manifest["config"]
    assert cfg == load_config("configs/runs/smoke.yaml")
    assert manifest["config_hash"] == resolved_config_hash(cfg)
    assert manifest["active_release"] == "2026-Q2"


def test_bench_run_active_release_filters_future_scenarios(tmp_path):
    config_path = tmp_path / "release-run.yaml"
    config_path.write_text("""
schema_version: "1.0.0"
run_seed: 12345
weeks: 1
epochs: 1
mode: mechanistic
runner: {parallel: 1, persist_traces: false}
cache: {enabled: true}
scenarios:
  - import: "active.yaml"
  - import: "future.yaml"
models:
  - import: "model.yaml"
telemetry: {}
""")
    (tmp_path / "model.yaml").write_text(
        "id: mechanistic\nprovider: mechanistic\nmodel: mechanistic\n"
    )
    (tmp_path / "active.yaml").write_text(_scenario_yaml("active", "2026-Q1"))
    (tmp_path / "future.yaml").write_text(_scenario_yaml("future", "2027-Q1"))

    result = CliRunner().invoke(
        bench,
        [
            "run",
            "--config",
            str(config_path),
            "--active-release",
            "2026-Q2",
            "--runs-dir",
            str(tmp_path),
            "--run-id",
            "release-smoke",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads(
        (tmp_path / "release-smoke.eval" / "manifest.json").read_text()
    )
    assert manifest["active_release"] == "2026-Q2"
    assert [
        scenario["scenario_id"] for scenario in manifest["config"]["scenarios"]
    ] == ["active"]


def _scenario_yaml(scenario_id: str, release_date: str) -> str:
    return f"""
scenario_id: {scenario_id}
demand_pattern: step
params: {{low: 4, high: 8, step_week: 5}}
weeks: 1
costs: {{holding: 0.5, backlog: 1.0}}
scenario_seed: 42
release_date: "{release_date}"
removal_date: null
"""
