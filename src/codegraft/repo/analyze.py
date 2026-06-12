"""Single deterministic-analysis entry point.

Runs the whole model-free pipeline — discover → summarize → rank → snippets —
and returns a bundle. Both `inspect` (Phase 3) and the planning service
(Phase 4) build on this; keeping it in one place means they agree on exactly
what evidence a request produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codegraft.config import Config
from codegraft.models.repo import RankedFile, RepoScan, RepoSummary, Snippet
from codegraft.repo.discover import discover_repo
from codegraft.repo.rank import rank_files
from codegraft.repo.snippets import extract_snippets
from codegraft.repo.summarize import summarize
from codegraft.utils.text import ranking_signal


@dataclass
class RepoAnalysis:
    """Everything the deterministic layer produces for one request."""

    request: str          # full request text — goes to the model
    ranking_signal: str   # focused signal actually used to rank/snippet
    scan: RepoScan
    summary: RepoSummary
    ranked: list[RankedFile]
    snippets: list[Snippet]

    @property
    def context_chars(self) -> int:
        return sum(s.char_count for s in self.snippets)


def analyze_repo(
    request: str, root: Path, config: Config, subdir: str | None = None
) -> RepoAnalysis:
    """Discover, summarize, rank, and extract snippets for *request*.

    Ranking and snippet selection use a focused *signal* derived from the
    request (so a long, constraint-heavy request doesn't dilute file ranking),
    while the full request is preserved for the planning prompt.
    """

    signal = ranking_signal(request)
    scan = discover_repo(root, config, subdir=subdir)
    summary = summarize(scan)
    ranked = rank_files(signal, scan, summary, config)
    snippets = extract_snippets(signal, ranked, scan, config)
    return RepoAnalysis(
        request=request,
        ranking_signal=signal,
        scan=scan,
        summary=summary,
        ranked=ranked,
        snippets=snippets,
    )
