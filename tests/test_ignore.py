"""Tests for the filesystem fallback and .gitignore replication (no git)."""

from __future__ import annotations

from pathlib import Path

from codegraft.config import Config
from codegraft.repo.discover import discover_repo
from codegraft.repo.ignore import filesystem_scan
from tests.conftest import write


def _force_fallback_scan(root: Path):
    config = Config.load(root)
    config.repo.prefer_git_ls_files = False  # never call git
    return discover_repo(root, config)


def test_fallback_used_when_git_disabled(tmp_path: Path) -> None:
    write(tmp_path, "a.py")
    scan = _force_fallback_scan(tmp_path)
    assert scan.used_git is False
    assert "a.py" in {f.path for f in scan.files}


def test_root_gitignore_respected(tmp_path: Path) -> None:
    write(tmp_path, "keep.py")
    write(tmp_path, "skip.log")
    write(tmp_path, ".gitignore", "*.log\n")

    paths = filesystem_scan(tmp_path)
    assert "keep.py" in paths
    assert "skip.log" not in paths


def test_ignored_directory_is_pruned(tmp_path: Path) -> None:
    write(tmp_path, "src/app.py")
    write(tmp_path, "build/output.py")
    write(tmp_path, ".gitignore", "build/\n")

    paths = filesystem_scan(tmp_path)
    assert "src/app.py" in paths
    assert not any(p.startswith("build/") for p in paths)


def test_nested_gitignore_scoping(tmp_path: Path) -> None:
    """A nested .gitignore only affects its own subtree."""

    write(tmp_path, "pkg/keep.tmp")  # ignored by pkg/.gitignore
    write(tmp_path, "pkg/code.py")
    write(tmp_path, "other/keep.tmp")  # NOT ignored — different subtree
    write(tmp_path, "pkg/.gitignore", "*.tmp\n")

    paths = filesystem_scan(tmp_path)
    assert "pkg/code.py" in paths
    assert "pkg/keep.tmp" not in paths
    assert "other/keep.tmp" in paths


def test_git_dir_always_skipped(tmp_path: Path) -> None:
    write(tmp_path, ".git/config", "[core]\n")
    write(tmp_path, "real.py")

    paths = filesystem_scan(tmp_path)
    assert "real.py" in paths
    assert not any(p.startswith(".git/") for p in paths)


def test_fallback_applies_safety_denylist(tmp_path: Path) -> None:
    write(tmp_path, "app.py")
    write(tmp_path, ".env", "SECRET=1\n")
    scan = _force_fallback_scan(tmp_path)

    paths = {f.path for f in scan.files}
    reasons = {s.path: s.reason for s in scan.skipped}
    assert "app.py" in paths
    assert ".env" not in paths and reasons[".env"] == "secret"


def test_extra_excludes_glob_applied(tmp_path: Path) -> None:
    write(tmp_path, "app.py")
    write(tmp_path, "node_modules/dep/index.js")
    config = Config.load(tmp_path)
    config.repo.prefer_git_ls_files = False
    scan = discover_repo(tmp_path, config)

    paths = {f.path for f in scan.files}
    assert "app.py" in paths
    assert not any("node_modules" in p for p in paths)
