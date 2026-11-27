"""CLI smoke tests (typer CliRunner) with isolated runs/ and index paths."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from experimental_system.cli import app

REPO = Path(__file__).resolve().parents[1]
runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(REPO)  # default config paths are relative to the repository root
    monkeypatch.setenv("EXPSYS_RUNS_DIR", str(tmp_path / "runs"))
    for name in ("OPENROUTER_API_KEY", "DEFAULT_MODEL", "EXPSYS_REQUIRE_APPROVAL"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_scenarios_lists_demos() -> None:
    result = runner.invoke(app, ["scenarios"])
    assert result.exit_code == 0
    assert "ising_ground_state" in result.output and "two_foci_coupling" in result.output


def test_run_and_show(isolated: Path) -> None:
    result = runner.invoke(app, ["run", "--scenario", "runner_out_of_range", "--llm", "fake"])
    assert result.exit_code == 0, result.output
    assert ": DONE" in result.output and "validator rejected" in result.output
    [run_dir] = list((isolated / "runs").iterdir())
    assert (run_dir / "final_report.md").is_file()
    shown = runner.invoke(app, ["show", run_dir.name])
    assert shown.exit_code == 0 and "DONE" in shown.output
    assert runner.invoke(app, ["show", "missing"]).exit_code == 1


def test_run_with_approval_denied(isolated: Path) -> None:
    result = runner.invoke(
        app, ["run", "--scenario", "runner_out_of_range", "--approve"], input="n\n"
    )
    assert result.exit_code == 0, result.output
    assert "sim_laser.set_power(power=50.0 mW)" in result.output
    assert "ABORTED" in result.output


def test_config_errors_are_clean(isolated: Path) -> None:
    fake_without_scenario = runner.invoke(app, ["run", "task", "--llm", "fake"])
    assert fake_without_scenario.exit_code == 1
    assert "--scenario" in fake_without_scenario.output
    no_key = runner.invoke(app, ["run", "task", "--llm", "openrouter"])
    assert no_key.exit_code == 1 and "OPENROUTER_API_KEY" in no_key.output
    assert not (isolated / "runs").exists()  # nothing created before config is valid
    unknown = runner.invoke(app, ["run", "--scenario", "nope"])
    assert unknown.exit_code == 1 and "unknown scenario" in unknown.output
