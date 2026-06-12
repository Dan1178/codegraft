"""Repository discovery orchestrator.

Ties the discovery stages into a single deterministic pass:

1. Get candidate paths: git ls-files (preferred) or a filesystem walk fallback.
2. Drop anything matching the config ``extra_excludes`` globs.
3. Drop anything the safety denylist flags (secrets, oversized, generated, binary).
4. Cap the candidate list at ``max_candidate_files``.

The result is a typed :class:`RepoScan` with kept files, skip reasons, and
provenance (git vs. fallback) — the input every later stage builds on.
"""

from __future__ import annotations

from pathlib import Path

from pathspec import PathSpec

from codegraft.config import Config
from codegraft.errors import RepoError
from codegraft.models.repo import RepoFile, RepoScan, SkippedFile
from codegraft.repo import safety
from codegraft.repo.git_scan import git_scan
from codegraft.repo.ignore import filesystem_scan


def discover_repo(root: Path, config: Config, subdir: str | None = None) -> RepoScan:
    """Scan *root* and return a filtered, typed :class:`RepoScan`.

    If *subdir* is given, only candidates under that repo-relative directory are
    kept — and the expensive per-file stat/binary-sniff is skipped for everything
    outside it, which is the point of scoping a large monorepo.
    """

    root = root.resolve()
    if not root.is_dir():
        raise RepoError(f"not a directory: {root}")

    extra_spec = PathSpec.from_lines("gitignore", config.repo.extra_excludes)

    candidates, used_git = _candidates(root, config)
    if subdir:
        prefix = subdir.replace("\\", "/").strip("/")
        if not (root / prefix).is_dir():
            raise RepoError(f"--subdir not found in repo: {prefix}")
        candidates = [
            (rel, tracked)
            for rel, tracked in candidates
            if rel == prefix or rel.startswith(prefix + "/")
        ]

    files: list[RepoFile] = []
    skipped: list[SkippedFile] = []
    truncated = False

    for rel, tracked in candidates:
        if extra_spec.match_file(rel):
            skipped.append(SkippedFile(path=rel, reason="excluded"))
            continue

        abs_path = root / rel
        try:
            size = abs_path.stat().st_size
        except OSError:
            skipped.append(SkippedFile(path=rel, reason="unreadable"))
            continue

        reason = safety.classify(rel, abs_path, size, config.repo.max_file_bytes)
        if reason is not None:
            skipped.append(SkippedFile(path=rel, reason=reason))
            continue

        files.append(RepoFile(path=rel, size_bytes=size, tracked=tracked))
        if len(files) >= config.repo.max_candidate_files:
            truncated = True
            break

    return RepoScan(
        root=str(root),
        files=files,
        skipped=skipped,
        used_git=used_git,
        truncated=truncated,
    )


def _candidates(root: Path, config: Config) -> tuple[list[tuple[str, bool]], bool]:
    """Return ``([(rel_path, tracked), ...], used_git)`` in stable sorted order."""

    git_result = git_scan(root) if config.repo.prefer_git_ls_files else None

    if git_result is not None:
        tracked, untracked = git_result
        ordered: list[tuple[str, bool]] = [(p, True) for p in sorted(tracked)]
        ordered += [(p, False) for p in sorted(untracked) if p not in tracked]
        return ordered, True

    # Filesystem fallback: no git knowledge, so "tracked" is assumed True.
    paths = filesystem_scan(root, respect_gitignore=config.repo.respect_gitignore)
    return [(p, True) for p in sorted(paths)], False
