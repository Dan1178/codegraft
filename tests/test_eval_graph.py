"""Tests for the graph-tool validators (eval-impact / eval-tests).

Aggregation is tested as pure functions (no git); the git wiring gets one
end-to-end smoke test per validator, skipped when git is unavailable.
"""

from __future__ import annotations

from pathlib import Path

from codegraft.config import Config
from codegraft.evaluation_graph import (
    AffectedTestsCase,
    AffectedTestsReport,
    ImpactCase,
    ImpactReport,
    run_impact_eval,
    run_tests_eval,
)
from tests.conftest import init_git_repo, git, requires_git, write


# --- Pure aggregation ---


def test_impact_report_aggregates() -> None:
    report = ImpactReport(
        transitive=True,
        cases=[
            ImpactCase("a", "s", gold_total=3, pairs=3, linked_pairs=3),  # 1.00
            ImpactCase("b", "s", gold_total=2, pairs=1, linked_pairs=0),  # 0.00
            ImpactCase("c", "s", gold_total=1, pairs=0, linked_pairs=0),  # not evaluable
        ],
    )

    assert len(report.scored) == 2
    assert report.mean_pair_recall == 0.5          # (1.0 + 0.0) / 2
    assert report.micro_pair_recall == 0.75        # 3 linked / 4 pairs


def test_test_select_report_aggregates() -> None:
    report = AffectedTestsReport(
        cases=[
            AffectedTestsCase("a", "s", changed_source=2, gold_tests=4, selected=3),  # 0.75
            AffectedTestsCase("b", "s", changed_source=1, gold_tests=1, selected=1),  # 1.00
            AffectedTestsCase("c", "s", changed_source=0, gold_tests=2, selected=0),  # test-only: skip
            AffectedTestsCase("d", "s", changed_source=3, gold_tests=0, selected=0),  # no tests: skip
        ],
    )

    assert len(report.scored) == 2
    assert report.mean_recall == 0.875             # (0.75 + 1.0) / 2
    assert report.micro_recall == 0.8              # 4 selected / 5 gold tests


# --- Git-backed smoke tests ---


def _config(root: Path) -> Config:
    config = Config.load(root)
    config.repo.prefer_git_ls_files = True  # the validators read git history
    return config


@requires_git
def test_run_tests_eval_recovers_cochanged_test(tmp_path: Path) -> None:
    """A commit that changes a module and its importing test scores recall 1.0."""

    init_git_repo(tmp_path)
    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "app/core.py", "def core_fn():\n    return 1\n")
    write(
        tmp_path,
        "tests/test_core.py",
        "from app.core import core_fn\ndef test_it():\n    assert core_fn() == 1\n",
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "add core and its test")
    sha = git(tmp_path, "rev-parse", "HEAD").stdout.decode().strip()

    report = run_tests_eval(tmp_path, _config(tmp_path), [sha])

    assert len(report.scored) == 1
    assert report.cases[0].gold_tests == 1
    assert report.cases[0].selected == 1
    assert report.mean_recall == 1.0


@requires_git
def test_run_impact_eval_links_cochanged_pair(tmp_path: Path) -> None:
    """A commit changing a module and a file that imports it has a linked pair."""

    init_git_repo(tmp_path)
    # Commit the manifest first so the scored commit's gold set is exactly the
    # two source files (an all-in-one initial commit would add pyproject too).
    write(tmp_path, "pyproject.toml", "[project]\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "scaffold")
    write(tmp_path, "app/core.py", "def core_fn():\n    return 1\n")
    write(tmp_path, "app/user.py", "from app.core import core_fn\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "core plus a user of it")
    sha = git(tmp_path, "rev-parse", "HEAD").stdout.decode().strip()

    report = run_impact_eval(tmp_path, _config(tmp_path), [sha])

    assert len(report.scored) == 1
    assert report.cases[0].pairs == 1
    assert report.cases[0].linked_pairs == 1
    assert report.mean_pair_recall == 1.0
