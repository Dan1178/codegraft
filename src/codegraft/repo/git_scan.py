"""Git-aware file discovery via ``git ls-files``.

This is the primary discovery path. Git already understands ``.gitignore`` (root
and nested), ``.git/info/exclude``, and the user's global excludes, and it
correctly keeps *tracked* files listed even when a later ignore rule would match
them — exactly the semantics we want when analyzing a real repository.

We run two scoped calls so we can label each file tracked vs. untracked:
- ``git ls-files --cached``               -> tracked files
- ``git ls-files --others --exclude-standard`` -> untracked-but-not-ignored files

``--full-name`` yields repo-root-relative, forward-slash paths; ``-z`` uses NUL
separators so filenames with spaces, quotes, or unicode survive intact (no
``core.quotepath`` mangling).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def git_available() -> bool:
    """True if a ``git`` executable is on PATH."""

    return shutil.which("git") is not None


def is_git_worktree(root: Path) -> bool:
    """True if *root* is inside a git working tree."""

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == b"true"


def _run_ls_files(root: Path, extra_args: list[str]) -> set[str]:
    """Run ``git ls-files`` with NUL output and return a set of relative paths."""

    cmd = ["git", "-C", str(root), "ls-files", "--full-name", "-z", *extra_args]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        # Surface as "no result"; the caller falls back to the filesystem walk.
        raise subprocess.SubprocessError(
            result.stderr.decode("utf-8", "replace").strip() or "git ls-files failed"
        )
    # NUL-separated; trailing NUL produces an empty final field.
    raw = result.stdout.split(b"\0")
    return {
        chunk.decode("utf-8", "surrogateescape")
        for chunk in raw
        if chunk
    }


def git_scan(root: Path) -> tuple[set[str], set[str]] | None:
    """Discover files via git.

    Returns ``(tracked, untracked)`` sets of repo-relative paths, or ``None`` if
    git is unavailable or *root* is not a git working tree (signalling the
    caller to use the filesystem fallback).
    """

    if not git_available() or not is_git_worktree(root):
        return None
    try:
        tracked = _run_ls_files(root, ["--cached"])
        untracked = _run_ls_files(root, ["--others", "--exclude-standard"])
    except (OSError, subprocess.SubprocessError):
        return None
    return tracked, untracked
