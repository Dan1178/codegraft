"""Reverse-dependency queries over the heuristic import graph.

A thin, read-only query layer on top of :func:`build_import_graph`. It answers
two related questions an agent has *before* it edits:

- ``impact_of(file)`` — "what depends on this?" (blast-radius triage), and
- ``affected_tests(changed)`` — "which tests cover these changes?" (Phase 3).

Both are the transpose of the forward import scan codegraft already runs for
ranking, so they cost an O(candidates) graph build and no model call. Resolution
is heuristic (the scan misses dynamic imports / re-exports / ambiguous
basenames), so every result is stamped ``resolution: "heuristic"`` — blast-radius
triage, never a correctness oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codegraft.config import Config
from codegraft.models.repo import RepoScan, RepoSummary
from codegraft.repo.imports import ImportGraph, build_import_graph


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def resolve_target(target: str, scan: RepoScan) -> tuple[str | None, list[str]]:
    """Resolve a user-given *target* to a single candidate path.

    Accepts a repo-relative path, a path suffix (``css/style.css`` matches
    ``static/css/style.css``), or a bare basename. Mirrors ``_named_file_hit``'s
    matching so the reverse view agrees with how named-file ranking resolves
    mentions. Returns ``(path, [])`` on a unique match, ``(None, candidates)``
    when a basename/suffix is ambiguous (so the caller can list them), and
    ``(None, [])`` when nothing matches.
    """

    norm = target.replace("\\", "/").strip().lstrip("./").lower()
    paths = [f.path for f in scan.files]
    by_lower = {p.lower(): p for p in paths}

    if norm in by_lower:
        return by_lower[norm], []

    if "/" in norm:
        matches = sorted(p for p in paths if p.lower().endswith("/" + norm))
    else:
        matches = sorted(p for p in paths if _basename(p).lower() == norm)
        if not matches:  # try matching the stem (extension-less mention)
            matches = sorted(
                p for p in paths if _basename(p).lower().rsplit(".", 1)[0] == norm
            )

    if len(matches) == 1:
        return matches[0], []
    return None, matches


def reverse_closure(graph: ImportGraph, seeds: set[str]) -> set[str]:
    """Every file that *transitively* imports any of *seeds* (excludes the seeds).

    A bounded reverse-BFS over ``graph.reverse``; the ``reached`` set makes import
    cycles terminate. This is the engine behind transitive ``impact_of`` and
    behind ``affected_tests`` (Phase 3): a test that imports a module that imports
    a changed file must still be reached.
    """

    seeds = set(seeds)
    reached: set[str] = set()
    stack = list(seeds)
    while stack:
        node = stack.pop()
        for importer in graph.importers_of(node):
            if importer not in reached and importer not in seeds:
                reached.add(importer)
                stack.append(importer)
    return reached


@dataclass
class ImpactResult:
    """The blast radius of a target file: who imports it, directly and beyond."""

    target: str                              # the raw target as asked
    resolved: str | None                     # the candidate it resolved to, if unique
    imported_by: list[str] = field(default_factory=list)   # direct importers, sorted
    transitive: list[str] = field(default_factory=list)    # further reverse closure
    ambiguous: list[str] = field(default_factory=list)     # candidates when target was ambiguous
    resolution: str = "heuristic"

    @property
    def found(self) -> bool:
        return self.resolved is not None


def impact_of(
    target: str,
    scan: RepoScan,
    root: Path,
    config: Config,
    *,
    transitive: bool = False,
    graph: ImportGraph | None = None,
) -> ImpactResult:
    """Files that depend on *target*, for blast-radius triage before an edit.

    V1 returns the **direct importers**; ``transitive=True`` adds the full reverse
    closure (everything that reaches *target* through a chain of imports). Pass a
    prebuilt *graph* to avoid rebuilding it when several queries run in one turn.
    A target that nobody imports yields an empty ``imported_by`` (not an error);
    an ambiguous bare basename yields ``ambiguous`` candidates and no resolution.
    """

    if graph is None:
        graph = build_import_graph(scan, root, config)

    resolved, candidates = resolve_target(target, scan)
    if resolved is None:
        return ImpactResult(target=target, resolved=None, ambiguous=candidates)

    direct = sorted(graph.importers_of(resolved))
    trans: list[str] = []
    if transitive:
        closure = reverse_closure(graph, {resolved})
        trans = sorted(closure - set(direct))
    return ImpactResult(
        target=target, resolved=resolved, imported_by=direct, transitive=trans
    )


@dataclass
class AffectedTests:
    """Tests that (heuristically) depend on a set of changed files."""

    changed: list[str]                       # the changed files asked about (resolved)
    tests: list[str] = field(default_factory=list)   # reachable test files, sorted
    unresolved: list[str] = field(default_factory=list)  # changed inputs not found in the scan
    completeness: str = "heuristic"


def _is_test_path(path: str, test_paths: set[str]) -> bool:
    """Membership check matching ``rank._stage1_signals``' ``test`` signal exactly,
    so "what counts as a test" stays consistent across the codebase."""

    return path in test_paths or any(
        path.startswith(t + "/") or path == t for t in test_paths
    )


def affected_tests(
    changed: list[str],
    scan: RepoScan,
    summary: RepoSummary,
    root: Path,
    config: Config,
    *,
    graph: ImportGraph | None = None,
) -> AffectedTests:
    """Test files reverse-reachable from *changed*, intersected with the repo's tests.

    Selection only — codegraft never runs anything. The reverse closure is
    transitive (a test importing a module that imports a changed file is
    selected), so it is a fast-feedback *hint*: being heuristic it can miss tests
    (false negatives), and must never replace a full-suite run before merge.
    """

    if graph is None:
        graph = build_import_graph(scan, root, config)

    test_paths = set(summary.test_paths)
    resolved: set[str] = set()
    unresolved: list[str] = []
    for item in changed:
        path, _candidates = resolve_target(item, scan)
        if path is None:
            unresolved.append(item)
        else:
            resolved.add(path)

    closure = reverse_closure(graph, resolved)
    # A changed file can itself be a test; include it so editing a test selects it.
    reachable = closure | resolved
    tests = sorted(p for p in reachable if _is_test_path(p, test_paths))
    return AffectedTests(
        changed=sorted(resolved), tests=tests, unresolved=sorted(unresolved)
    )
