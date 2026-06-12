"""Text tokenization for keyword extraction and symbol matching.

Deterministic and dependency-free. The same tokenizer is used to turn a feature
request into keywords and to break identifiers like ``getUserRole`` /
``user_role`` into comparable tokens, so path/symbol overlap actually lines up.
"""

from __future__ import annotations

import re

# Split on non-alphanumeric AND on camelCase boundaries.
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+|[0-9]+")
_WORD = re.compile(r"[A-Za-z0-9]+")

# Common English + programming filler that adds noise to overlap scoring.
STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
        "add", "added", "adding", "support", "feature", "implement", "create",
        "make", "new", "use", "using", "via", "that", "this", "is", "are", "be",
        "should", "would", "can", "will", "into", "from", "by", "as", "at", "it",
        "we", "want", "need", "please", "able", "allow", "when", "then", "so",
    }
)


def split_identifier(name: str) -> list[str]:
    """Break an identifier into lowercase word tokens.

    >>> split_identifier("getUserRole")
    ['get', 'user', 'role']
    >>> split_identifier("user_role_v2")
    ['user', 'role', 'v2']
    """

    return [m.group(0).lower() for m in _CAMEL.finditer(name)]


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens from arbitrary text, camelCase-aware."""

    tokens: list[str] = []
    for word in _WORD.findall(text):
        tokens.extend(split_identifier(word))
    return tokens


def extract_keywords(request: str, min_len: int = 3) -> set[str]:
    """Normalized, de-duplicated, stopword-filtered keywords from a request."""

    return {
        tok
        for tok in tokenize(request)
        if len(tok) >= min_len and tok not in STOPWORDS
    }


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s")


def ranking_signal(text: str, max_chars: int = 240) -> str:
    """Derive a focused ranking signal from a (possibly long) feature request.

    The *full* request still goes to the model — but a long, constraint-laden
    request floods keyword extraction and dilutes file ranking. So for long
    inputs we focus on the part that states the goal: a leading markdown heading,
    else the first line, else the first sentence. Short requests pass through
    unchanged, preserving today's behaviour.
    """

    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped

    # Prefer a leading markdown heading (e.g. "# Add an OpenAI provider").
    for line in stripped.splitlines():
        if line.lstrip().startswith("#"):
            heading = line.lstrip("#").strip()
            if heading:
                return heading

    first_line = next((ln.strip() for ln in stripped.splitlines() if ln.strip()), stripped)
    if len(first_line) > max_chars:
        # A single long paragraph: take its first sentence.
        return _SENTENCE_SPLIT.split(first_line, maxsplit=1)[0]
    return first_line
