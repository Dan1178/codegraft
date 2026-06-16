"""Retrospective validators for the reverse-dependency tools.

The ranking validator (``evaluation.py``) asks "did `inspect` surface the files a
commit changed?". These ask the analogous question for the *graph* tools, so each
new tool ships with a measured baseline of the value it adds — not just tests
that it runs.

- :func:`run_impact_eval` scores ``impact_of`` as a **co-change predictor**: of
  the file *pairs* that real commits changed together, how many are linked by an
  import path? That is exactly "would ``impact_of`` on one of them have surfaced
  the other" — the blast-radius claim, measured against history.

Like ``evaluation.py`` this is deliberately model-free and reproducible (no API
key, no LLM), and carries the same honest caveat: the graph is built over the
*current* working tree, not a checkout of each commit's parent, so co-changed
files that were since deleted/renamed simply drop out of the candidate set.

The import graph does **not** depend on the request, so unlike the ranking eval
it is built **once** and reused across every commit — these validators do not
spin per-commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from codegraft.config import Config
from codegraft.repo.discover import discover_repo
from codegraft.repo.graph import reverse_closure
from codegraft.repo.git_scan import commit_changed_files, commit_subject
from codegraft.repo.imports import ImportGraph, build_import_graph


@dataclass
class ImpactCase:
    """How well the import graph linked one commit's co-changed files."""

    sha: str
    subject: str
    gold_total: int          # changed files that are analysis candidates
    pairs: int               # co-changed candidate pairs, C(gold_total, 2)
    linked_pairs: int        # pairs connected by an import path (either direction)

    @property
    def evaluable(self) -> bool:
        """A commit needs ≥2 candidate files to form a co-change pair."""

        return self.pairs > 0

    @property
    def pair_recall(self) -> float:
        return self.linked_pairs / self.pairs if self.pairs else 0.0


@dataclass
class ImpactReport:
    """Per-commit co-change linkage plus aggregates for one configuration."""

    transitive: bool
    cases: list[ImpactCase] = field(default_factory=list)

    @property
    def scored(self) -> list[ImpactCase]:
        return [c for c in self.cases if c.evaluable]

    @property
    def mean_pair_recall(self) -> float:
        """Macro average — each commit weighted equally."""

        scored = self.scored
        return sum(c.pair_recall for c in scored) / len(scored) if scored else 0.0

    @property
    def micro_pair_recall(self) -> float:
        """Micro average — every co-change pair weighted equally."""

        total = sum(c.pairs for c in self.scored)
        linked = sum(c.linked_pairs for c in self.scored)
        return linked / total if total else 0.0


def _linked(
    a: str,
    b: str,
    graph: ImportGraph,
    closures: dict[str, set[str]],
    transitive: bool,
) -> bool:
    """True if *a* and *b* are connected by an import edge (either direction).

    For ``transitive`` we use each file's full reverse closure (cached); for the
    direct view we use only immediate importers — the exact ``impact_of`` levels.
    """

    if transitive:
        return b in closures[a] or a in closures[b]
    return a in graph.importers_of(b) or b in graph.importers_of(a)


def run_impact_eval(
    root: Path,
    config: Config,
    shas: list[str],
    *,
    transitive: bool = True,
) -> ImpactReport:
    """Score the import graph as a co-change predictor over *shas*.

    Builds the scan and graph once (request-independent), then for each commit
    measures the fraction of its co-changed candidate pairs that the graph links.
    """

    scan = discover_repo(root, config)
    graph = build_import_graph(scan, root, config)
    candidates = {f.path for f in scan.files}

    # Reverse closures are reused across commits and pairs — compute each once.
    closures: dict[str, set[str]] = {}

    def closure_of(path: str) -> set[str]:
        if path not in closures:
            closures[path] = reverse_closure(graph, {path})
        return closures[path]

    report = ImpactReport(transitive=transitive)
    for sha in shas:
        subject = commit_subject(root, sha)
        gold = sorted(commit_changed_files(root, sha) & candidates)
        if transitive:
            for path in gold:
                closure_of(path)  # warm the cache for this commit's files
        pairs = list(combinations(gold, 2))
        linked = sum(1 for a, b in pairs if _linked(a, b, graph, closures, transitive))
        report.cases.append(
            ImpactCase(
                sha=sha,
                subject=subject,
                gold_total=len(gold),
                pairs=len(pairs),
                linked_pairs=linked,
            )
        )
    return report
