import json
from pathlib import Path

from click.testing import CliRunner

from src.bench.cli._common import resolve_bundle
from src.bench.cli.main import bench
from src.bench.run import run_bundle


def test_resolve_bundle_supports_full_path_latest_prefix_and_env(tmp_path, monkeypatch):
    first = run_bundle(turns=1, root=tmp_path, run_id="alpha-run")
    latest = run_bundle(turns=1, root=tmp_path, run_id="bravo-run")

    assert resolve_bundle(str(first)) == first.resolve()
    assert resolve_bundle("latest", tmp_path) == latest.resolve()
    assert resolve_bundle("bravo", tmp_path) == latest.resolve()

    monkeypatch.setenv("BEERGAME_RUNS_DIR", str(tmp_path))
    assert resolve_bundle("alpha") == first.resolve()


def test_resolve_bundle_reports_ambiguous_prefix(tmp_path):
    run_bundle(turns=1, root=tmp_path, run_id="same-one")
    run_bundle(turns=1, root=tmp_path, run_id="same-two")

    runner = CliRunner()
    result = runner.invoke(bench, ["report", "same", "--runs-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "Ambiguous bundle prefix" in result.output


def test_bench_help_lists_issue_9_subcommands():
    result = CliRunner().invoke(bench, ["--help"])

    assert result.exit_code == 0
    for command in ("run", "report", "list", "show", "compare"):
        assert command in result.output
    assert "#9" in result.output


def test_bench_run_report_list_show_and_json(tmp_path):
    runner = CliRunner()

    run_result = runner.invoke(
        bench,
        [
            "run",
            "--mode",
            "mechanistic",
            "--turns",
            "1",
            "--epochs",
            "2",
            "--runs-dir",
            str(tmp_path),
            "--run-id",
            "cli-smoke",
        ],
    )
    assert run_result.exit_code == 0, run_result.output
    bundle_path = Path(run_result.output.strip())
    assert bundle_path.exists()

    report_result = runner.invoke(bench, ["report", str(bundle_path)])
    assert report_result.exit_code == 0, report_result.output
    assert "Bundle:" in report_result.output
    assert "Metrics" in report_result.output

    json_result = runner.invoke(
        bench, ["report", "cli", "--runs-dir", str(tmp_path), "--format", "json"]
    )
    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.output)
    assert set(payload) == {"manifest", "metrics", "per_role", "per_model"}
    assert payload["manifest"]["run_id"] == "cli-smoke"

    list_result = runner.invoke(bench, ["list", "--runs-dir", str(tmp_path)])
    assert list_result.exit_code == 0, list_result.output
    assert "cli-smoke" in list_result.output
    assert "total_cost" in list_result.output

    show_result = runner.invoke(bench, ["show", "latest", "--runs-dir", str(tmp_path)])
    assert show_result.exit_code == 0, show_result.output
    assert "game_id" in show_result.output
    assert "total_cost" in show_result.output


def test_bench_show_game_drills_into_states_and_decisions(tmp_path):
    bundle_path = run_bundle(turns=1, root=tmp_path, run_id="detail")
    game_id = json.loads((bundle_path / "games.jsonl").read_text())["game_id"]

    result = CliRunner().invoke(
        bench, ["show", "detail", "--runs-dir", str(tmp_path), "--game", game_id]
    )

    assert result.exit_code == 0, result.output
    assert "States" in result.output
    assert "Decisions" in result.output
    assert "retailer" in result.output


def test_bench_future_flags_fail_clearly(tmp_path):
    result = CliRunner().invoke(
        bench,
        [
            "run",
            "--turns",
            "1",
            "--runs-dir",
            str(tmp_path),
            "--persist-traces",
        ],
    )

    assert result.exit_code != 0
    assert "--persist-traces is reserved for a follow-on issue" in result.output


def test_bench_run_cache_flags_are_mutually_exclusive(tmp_path):
    result = CliRunner().invoke(
        bench,
        [
            "run",
            "--turns",
            "1",
            "--runs-dir",
            str(tmp_path),
            "--no-cache",
            "--refresh-cache",
        ],
    )

    assert result.exit_code != 0
    assert "--no-cache and --refresh-cache are mutually exclusive" in result.output


def test_bench_compare_reports_missing_models(tmp_path):
    bundle_path = run_bundle(turns=1, root=tmp_path, run_id="compare")

    result = CliRunner().invoke(
        bench,
        [
            "compare",
            str(bundle_path),
            "--baseline",
            "a",
            "--challenger",
            "b",
        ],
    )

    assert result.exit_code != 0
    assert "Model not found: a, b" in result.output
