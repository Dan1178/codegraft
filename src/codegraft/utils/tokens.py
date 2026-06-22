"""Rough token estimation for the "tokens saved" metric.

This deliberately uses a cheap ~4-chars-per-token heuristic, **not** ``tiktoken``
(that is OpenAI's tokenizer and undercounts Claude tokens) and **not** the
Anthropic ``count_tokens`` endpoint (which would cost a network call / key). The
numbers are presented to the user as estimates, and that's all they need to be:
the point is to show the *order of magnitude* of context that selective snippet
extraction avoids sending, not an exact bill.

**What the baseline is, and is not.** The honest alternative to codegraft's
bundle is *not* "send the entire repository" — no agent reads unrelated files to
implement one feature, so comparing against the whole codebase would inflate the
savings. The baseline is the set of files codegraft actually surfaced as
relevant, read **in full**: the realistic thing an agent would otherwise open.
The saved figure therefore measures the win from *snippet extraction* (bounded
slices of the right files) over reading those same files whole — a claim that
holds up to scrutiny.
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
    """Estimated cost of the snippet bundle vs. reading the selected files whole."""

    selected_files: int   # files codegraft surfaced (the snippet sources)
    baseline_chars: int   # those files, read in full
    bundle_chars: int     # the bounded snippets codegraft actually sends
    baseline_tokens: int
    bundle_tokens: int
    saved_tokens: int
    saved_pct: float

    def summary(self) -> str:
        """One-line human summary."""

        return (
            f"~{self.bundle_tokens:,} tokens sent vs ~{self.baseline_tokens:,} "
            f"to read the {self.selected_files} selected files in full "
            f"— ~{self.saved_tokens:,} saved ({self.saved_pct:.0f}%)"
        )


def estimate_savings(
    baseline_chars: int, bundle_chars: int, selected_files: int
) -> TokenEstimate:
    """Compute the token estimate for a bundle vs. reading the selected files whole.

    `baseline_chars` is the total size of the files codegraft surfaced as
    relevant, read in full (the realistic alternative an agent would otherwise
    open); `bundle_chars` is the size of the bounded snippets codegraft selected
    from those same files.
    """

    baseline_tokens = estimate_tokens(baseline_chars)
    bundle_tokens = estimate_tokens(bundle_chars)
    saved_tokens = max(0, baseline_tokens - bundle_tokens)
    saved_pct = (saved_tokens / baseline_tokens * 100) if baseline_tokens else 0.0
    return TokenEstimate(
        selected_files=selected_files,
        baseline_chars=baseline_chars,
        bundle_chars=bundle_chars,
        baseline_tokens=baseline_tokens,
        bundle_tokens=bundle_tokens,
        saved_tokens=saved_tokens,
        saved_pct=saved_pct,
    )
