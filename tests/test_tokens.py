"""Tests for the token-savings estimate."""

from __future__ import annotations

from pathlib import Path

from codegraft.config import Config
from codegraft.repo.analyze import analyze_repo
from codegraft.utils.tokens import estimate_savings, estimate_tokens
from tests.conftest import write


def test_estimate_tokens_basics() -> None:
    assert estimate_tokens(0) == 0
    assert estimate_tokens(-5) == 0
    assert estimate_tokens(4) == 1
    assert estimate_tokens(4000) == 1000  # ~4 chars/token


def test_estimate_savings_math() -> None:
    est = estimate_savings(baseline_chars=40_000, bundle_chars=8_000, candidate_files=12)
    assert est.baseline_tokens == 10_000
    assert est.bundle_tokens == 2_000
    assert est.saved_tokens == 8_000
    assert est.saved_pct == 80.0
    assert "saved" in est.summary()


def test_savings_never_negative() -> None:
    # A bundle larger than the baseline (degenerate) clamps to zero saved.
    est = estimate_savings(baseline_chars=100, bundle_chars=400, candidate_files=1)
    assert est.saved_tokens == 0
    assert est.saved_pct == 0.0


def test_empty_repo_is_safe() -> None:
    est = estimate_savings(baseline_chars=0, bundle_chars=0, candidate_files=0)
    assert est.baseline_tokens == 0
    assert est.saved_tokens == 0
    assert est.saved_pct == 0.0


def test_analysis_reports_savings(tmp_path: Path) -> None:
    # A repo where only some files are relevant: bundle should be smaller than
    # the full candidate set, so savings are positive.
    write(tmp_path, "app/auth.py", "def check_role(role):\n    return role\n" * 5)
    for i in range(6):
        write(tmp_path, f"app/unrelated{i}.py", "x = 1\n" * 200)  # bulk, irrelevant
    config = Config.load(tmp_path)
    config.repo.prefer_git_ls_files = False

    est = analyze_repo("check role", tmp_path, config).token_estimate()
    assert est.candidate_files >= 1
    assert est.bundle_tokens <= est.baseline_tokens
    assert est.saved_tokens >= 0
