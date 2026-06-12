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


def test_plan_stub_writes_markdown(tmp_path: Path) -> None:
    # --stub exercises the output path offline (no provider/API key needed).
    result = runner.invoke(
        app, ["plan", "Add RBAC to admin routes", "--repo", str(tmp_path), "--stub"]
    )
    assert result.exit_code == 0, result.stdout
    plans = list((tmp_path / "plans").glob("*.md"))
    assert len(plans) == 1
    content = plans[0].read_text(encoding="utf-8")
    assert content.startswith("# ")
    assert "## Files Reviewed" in content


def test_plan_dry_run_writes_nothing(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["plan", "Add caching", "--repo", str(tmp_path), "--stub", "--dry-run"]
    )
    assert result.exit_code == 0
    assert not (tmp_path / "plans").exists()


def test_plan_stdout(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["plan", "Add caching", "--repo", str(tmp_path), "--stub", "--stdout"]
    )
    assert result.exit_code == 0
    assert "# Add caching" in result.stdout
    assert not (tmp_path / "plans").exists()


def test_plan_requires_a_request(tmp_path: Path) -> None:
    result = runner.invoke(app, ["plan", "--repo", str(tmp_path), "--stub"])
    assert result.exit_code == 1


def test_plan_request_file(tmp_path: Path) -> None:
    req = tmp_path / "feature.md"
    req.write_text("Add soft-delete and restore endpoints", encoding="utf-8")
    result = runner.invoke(
        app, ["plan", "--repo", str(tmp_path), "--request-file", str(req), "--stub"]
    )
    assert result.exit_code == 0, result.stdout
    assert list((tmp_path / "plans").glob("*.md"))


def test_inspect_summary_only(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    result = runner.invoke(app, ["inspect", "--repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Pass a feature request" in result.stdout


def test_inspect_request_file(tmp_path: Path) -> None:
    (tmp_path / "auth.py").write_text("def check_role(role):\n    return role\n", encoding="utf-8")
    req = tmp_path / "feature.md"
    req.write_text(
        "# Add role checks\n\nLong body describing constraints and goals. " * 20,
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["inspect", "--repo", str(tmp_path), "--request-file", str(req)]
    )
    assert result.exit_code == 0
    # The focused ranking signal (the heading) is surfaced to the user.
    assert "Ranking signal" in result.stdout
    assert "Add role checks" in result.stdout


def test_plan_unknown_provider_errors(tmp_path: Path) -> None:
    # Error text goes to stderr (Rich err_console); the message itself is
    # asserted at the service layer in test_providers. Here we just confirm the
    # CLI surfaces an unknown provider as a clean non-zero exit, not a traceback.
    result = runner.invoke(
        app, ["plan", "Add x", "--repo", str(tmp_path), "--provider", "nope"]
    )
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
