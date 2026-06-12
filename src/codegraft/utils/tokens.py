"""Rough token estimation for the "tokens saved" metric.

This deliberately uses a cheap ~4-chars-per-token heuristic, **not** ``tiktoken``
(that is OpenAI's tokenizer and undercounts Claude tokens) and **not** the
Anthropic ``count_tokens`` endpoint (which would cost a network call / key). The
numbers are presented to the user as estimates, and that's all they need to be:
the point is to show the *order of magnitude* of context that selective snippet
extraction avoids sending, not an exact bill.
"""

from __future__ import annotations

from dataclasses import dataclass

CHARS_PER_TOKEN = 4  # rough English/code average; an estimate, not exact


def estimate_tokens(chars: int) -> int:
    """Estimate token count from a character count."""

    if chars <= 0:
        return 0
    return chars // CHARS_PER_TOKEN


@dataclass(frozen=True)
class TokenEstimate:
    """Estimated cost of the context bundle vs. sending all candidate files."""

    candidate_files: int
    baseline_chars: int   # all candidate files, in full
    bundle_chars: int     # what codegraft actually sends
    baseline_tokens: int
    bundle_tokens: int
    saved_tokens: int
    saved_pct: float

    def summary(self) -> str:
        """One-line human summary."""

        return (
            f"~{self.bundle_tokens:,} tokens sent vs ~{self.baseline_tokens:,} "
            f"for all {self.candidate_files} candidate files "
            f"— ~{self.saved_tokens:,} saved ({self.saved_pct:.0f}%)"
        )


def estimate_savings(
    baseline_chars: int, bundle_chars: int, candidate_files: int
) -> TokenEstimate:
    """Compute the token estimate for a bundle vs. the full candidate set.

    `baseline_chars` is the total size of every candidate file (the naive
    "dump the repo" alternative); `bundle_chars` is the size of the snippets
    codegraft actually selected.
    """

    baseline_tokens = estimate_tokens(baseline_chars)
    bundle_tokens = estimate_tokens(bundle_chars)
    saved_tokens = max(0, baseline_tokens - bundle_tokens)
    saved_pct = (saved_tokens / baseline_tokens * 100) if baseline_tokens else 0.0
    return TokenEstimate(
        candidate_files=candidate_files,
        baseline_chars=baseline_chars,
        bundle_chars=bundle_chars,
        baseline_tokens=baseline_tokens,
        bundle_tokens=bundle_tokens,
        saved_tokens=saved_tokens,
        saved_pct=saved_pct,
    )
