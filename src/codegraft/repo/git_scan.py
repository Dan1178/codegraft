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

import os
import shutil
import subprocess
from pathlib import Path

# Never let git block on input or prompt for credentials. This matters most when
# codegraft runs inside an MCP stdio server: there the process's stdin IS the
# JSON-RPC protocol pipe, so a child git process that inherits stdin (or prompts
# for a credential) can hang the entire tool call indefinitely. DEVNULL stdin +
# these env vars make git fail fast instead of blocking.
_GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}


def _run_git(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run a git command with stdin detached and prompts disabled."""

    return subprocess.run(
        ["git", *args],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        env=_GIT_ENV,
        timeout=timeout,
    )


def git_available() -> bool:
    """True if a ``git`` executable is on PATH."""

    return shutil.which("git") is not None


def is_git_worktree(root: Path) -> bool:
    """True if *root* is inside a git working tree."""

    try:
        result = _run_git(["-C", str(root), "rev-parse", "--is-inside-work-tree"], timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == b"true"


def _run_ls_files(root: Path, extra_args: list[str]) -> set[str]:
    """Run ``git ls-files`` with NUL output and return a set of relative paths."""

    result = _run_git(
        ["-C", str(root), "ls-files", "--full-name", "-z", *extra_args], timeout=120
    )
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


def recent_commit_shas(root: Path, n: int) -> list[str]:
    """The most recent *n* commit SHAs (newest first), excluding merge commits.

    Merges are skipped (``--no-merges``) because ``diff-tree`` reports no files
    for them by default, so they carry no usable gold set for evaluation.
    """

    result = _run_git(
        ["-C", str(root), "log", "--no-merges", f"-n{n}", "--format=%H"], timeout=30
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            result.stderr.decode("utf-8", "replace").strip() or "git log failed"
        )
    return [line for line in result.stdout.decode("utf-8", "replace").split("\n") if line]


def commit_subject(root: Path, sha: str) -> str:
    """The subject line (first line of the message) of *sha* — used as the request."""

    result = _run_git(
        ["-C", str(root), "show", "-s", "--format=%s", sha], timeout=30
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            result.stderr.decode("utf-8", "replace").strip() or f"git show {sha} failed"
        )
    return result.stdout.decode("utf-8", "replace").strip()


def commit_changed_files(root: Path, sha: str) -> set[str]:
    """Repo-relative paths changed by *sha* (the gold set for evaluation).

    ``--root`` makes the initial commit report its files; ``-z`` keeps paths with
    spaces/unicode intact and matches the forward-slash, root-relative form used
    everywhere else in codegraft.
    """

    result = _run_git(
        ["-C", str(root), "diff-tree", "--no-commit-id", "--name-only", "-r",
         "--root", "-z", sha],
        timeout=30,
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            result.stderr.decode("utf-8", "replace").strip()
            or f"git diff-tree {sha} failed"
        )
    return {
        chunk.decode("utf-8", "surrogateescape")
        for chunk in result.stdout.split(b"\0")
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
