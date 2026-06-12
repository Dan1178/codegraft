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
