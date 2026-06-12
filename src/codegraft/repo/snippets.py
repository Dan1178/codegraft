"""Bounded snippet extraction — the evidence actually sent to the model.

For each ranked file we select a small, relevant slice rather than the whole
file: the header/imports (cheap structural context) plus short windows around
keyword hits. Hard caps on lines-per-file and a total character budget keep the
prompt small and the cost predictable — token discipline is part of the product.
"""

from __future__ import annotations

from pathlib import Path

from codegraft.config import Config
from codegraft.models.repo import RankedFile, RepoScan, Snippet
from codegraft.utils.text import extract_keywords, tokenize

HEADER_LINES = 12   # top-of-file imports / module docstring
WINDOW = 3          # lines of context on each side of a keyword hit


def _line_has_keyword(line: str, keywords: set[str]) -> bool:
    return any(tok in keywords for tok in tokenize(line))


def _select_line_indices(
    lines: list[str], keywords: set[str], max_lines: int
) -> tuple[list[int], bool]:
    """Choose which line indices to keep. Returns (sorted_indices, truncated)."""

    keep: set[int] = set(range(min(HEADER_LINES, len(lines))))

    for i, line in enumerate(lines):
        if _line_has_keyword(line, keywords):
            lo = max(0, i - WINDOW)
            hi = min(len(lines), i + WINDOW + 1)
            keep.update(range(lo, hi))

    ordered = sorted(keep)
    truncated = False
    if len(ordered) > max_lines:
        ordered = ordered[:max_lines]
        truncated = True
    return ordered, truncated


def _render(lines: list[str], indices: list[int]) -> str:
    """Render selected lines with 1-based numbers and gap markers."""

    out: list[str] = []
    prev = -1
    for idx in indices:
        if prev != -1 and idx != prev + 1:
            out.append("        ...")
        out.append(f"{idx + 1:>6}  {lines[idx].rstrip()}")
        prev = idx
    return "\n".join(out)


def extract_snippets(
    request: str, ranked: list[RankedFile], scan: RepoScan, config: Config
) -> list[Snippet]:
    """Extract bounded snippets for the ranked files, under the global budget."""

    keywords = extract_keywords(request)
    root = Path(scan.root)
    budget = config.analysis.context_char_budget
    max_lines = config.analysis.max_snippet_lines_per_file

    snippets: list[Snippet] = []
    used_chars = 0

    for r in ranked:
        if used_chars >= budget:
            break
        try:
            text = (root / r.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()

        indices, truncated = _select_line_indices(lines, keywords, max_lines)
        if not indices:
            continue
        body = _render(lines, indices)

        # Respect the remaining budget; skip a snippet that would blow it.
        if used_chars + len(body) > budget and snippets:
            break

        snippets.append(
            Snippet(
                path=r.path,
                content=body,
                line_count=len(indices),
                char_count=len(body),
                truncated=truncated,
            )
        )
        used_chars += len(body)

    return snippets
