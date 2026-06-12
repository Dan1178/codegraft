"""Assemble a :class:`RepoSummary` from a scan.

Also decides the repo's *scale mode*, which downstream ranking/snippet stages
use to tighten caps so codegraft degrades gracefully on large repos instead of
pretending to understand a monorepo.
"""

from __future__ import annotations

from pathlib import Path

from codegraft.models.repo import RepoScan, RepoSummary
from codegraft.repo import detect
from codegraft.repo.tree import build_tree

# Candidate-count thresholds for graceful degradation.
MEDIUM_REPO_THRESHOLD = 500
LARGE_REPO_THRESHOLD = 2500


def repo_mode(file_count: int) -> str:
    """normal (<500) | medium (500–2499) | large (>=2500)."""

    if file_count >= LARGE_REPO_THRESHOLD:
        return "large"
    if file_count >= MEDIUM_REPO_THRESHOLD:
        return "medium"
    return "normal"


def summarize(scan: RepoScan) -> RepoSummary:
    """Build a compact, model-free summary from a completed scan."""

    paths = [f.path for f in scan.files]
    mix = detect.language_mix(paths)
    manifests = detect.find_manifests(paths)
    frameworks = detect.detect_frameworks(Path(scan.root), manifests)

    return RepoSummary(
        root=scan.root,
        file_count=scan.file_count,
        mode=repo_mode(scan.file_count),
        primary_language=detect.primary_language(mix),
        languages=mix,
        manifests=manifests,
        frameworks=frameworks,
        entry_points=detect.find_entry_points(paths),
        test_paths=detect.find_test_paths(paths),
        directory_tree=build_tree(paths),
    )
