"""Shared test helpers for building throwaway repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codegraft.repo.git_scan import git_available


def write(root: Path, rel: str, content: str = "x\n") -> Path:
    """Create a file (and parents) under *root* and return its path."""

    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in *root*, raising on failure."""

    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=True,
    )


def init_git_repo(root: Path) -> None:
    """Initialize a git repo with a deterministic identity."""

    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "config", "commit.gpgsign", "false")


requires_git = pytest.mark.skipif(
    not git_available(), reason="git executable not on PATH"
)
