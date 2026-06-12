"""CLI smoke tests for the Phase 1 surface."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from codegraft.cli import app
from codegraft.config import CONFIG_FILENAME

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "codegraft" in result.stdout


def test_init_writes_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / CONFIG_FILENAME).is_file()


def test_init_refuses_overwrite(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILENAME).write_text("# existing", encoding="utf-8")
    result = runner.invoke(app, ["init", "--repo", str(tmp_path)])
    assert result.exit_code == 1


def test_plan_writes_markdown(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["plan", "Add RBAC to admin routes", "--repo", str(tmp_path)]
    )
    assert result.exit_code == 0, result.stdout
    plans = list((tmp_path / "plans").glob("*.md"))
    assert len(plans) == 1
    content = plans[0].read_text(encoding="utf-8")
    assert content.startswith("# ")
    assert "## Files Reviewed" in content


def test_plan_dry_run_writes_nothing(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["plan", "Add caching", "--repo", str(tmp_path), "--dry-run"]
    )
    assert result.exit_code == 0
    assert not (tmp_path / "plans").exists()


def test_plan_stdout(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["plan", "Add caching", "--repo", str(tmp_path), "--stdout"]
    )
    assert result.exit_code == 0
    assert "# Add caching" in result.stdout
    assert not (tmp_path / "plans").exists()


def test_plan_requires_a_request(tmp_path: Path) -> None:
    result = runner.invoke(app, ["plan", "--repo", str(tmp_path)])
    assert result.exit_code == 1


def test_plan_request_file(tmp_path: Path) -> None:
    req = tmp_path / "feature.md"
    req.write_text("Add soft-delete and restore endpoints", encoding="utf-8")
    result = runner.invoke(
        app, ["plan", "--repo", str(tmp_path), "--request-file", str(req)]
    )
    assert result.exit_code == 0, result.stdout
    assert list((tmp_path / "plans").glob("*.md"))
