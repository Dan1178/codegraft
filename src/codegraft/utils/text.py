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


# Extensions that mark a token as an explicitly-named *file* in a request (e.g.
# "port the layout from static/css/style.css"). Gating on a known extension keeps
# ordinary prose like "version 2.0" or "e.g." from matching. Mirrors the
# languages codegraft detects; kept local so this module stays dependency-free.
_NAMED_FILE_EXTS: frozenset[str] = frozenset(
    {
        "py", "pyi", "js", "jsx", "mjs", "cjs", "ts", "tsx", "go", "rs",
        "java", "kt", "rb", "php", "cs", "cpp", "cc", "c", "h", "hpp",
        "swift", "scala", "sh", "sql", "html", "css", "scss", "vue",
        "svelte", "md", "yml", "yaml", "toml", "json",
    }
)
_NAMED_FILE_RE = re.compile(r"\b([\w./-]+\.([A-Za-z0-9]+))\b")


def extract_named_files(request: str) -> set[str]:
    """Filenames or paths a request names explicitly, e.g. ``style.css`` or
    ``static/css/style.css`` in "port the layout from static/css/style.css".

    Only tokens ending in a known source/asset/data extension match, so ordinary
    prose is ignored. Returns both the verbatim mention and its bare basename, so
    a candidate file can match whether the request named a full path or just a
    filename. Lowercased for case-insensitive matching against candidate paths.

    Run against the *full* request (not the focused ranking signal): a long
    request's file mention often lives in a later clause that ``ranking_signal``
    would otherwise truncate away.
    """

    found: set[str] = set()
    for mention, ext in _NAMED_FILE_RE.findall(request):
        if ext.lower() not in _NAMED_FILE_EXTS:
            continue
        mention = mention.lower().lstrip("./")
        if not mention:
            continue
        found.add(mention)
        if "/" in mention:
            found.add(mention.rsplit("/", 1)[-1])
    return found


# Request "intent" lexicons. A request that *unambiguously* leans frontend or
# backend lets the ranker modulate architectural role weights toward that side
# (see repo/rank.py). Kept small and high-signal, and all tokens are >= 3 chars
# so they survive `extract_keywords` filtering. A request that hits both lexicons
# (or neither) is "none" — we only steer when the lean is clear, so a mixed
# request competes flat rather than being mis-steered.
_FRONTEND_INTENT: frozenset[str] = frozenset(
    {
        "react", "frontend", "tsx", "jsx", "css", "scss", "tailwind",
        "component", "components", "template", "templates", "vue", "svelte",
        "style", "styles", "html", "typescript",
    }
)
_BACKEND_INTENT: frozenset[str] = frozenset(
    {
        "endpoint", "endpoints", "route", "routes", "migration", "migrations",
        "schema", "schemas", "orm", "query", "auth", "backend", "server",
        "database",
    }
)


def request_intent(keywords: set[str]) -> str:
    """Classify a request's architectural lean from its keywords.

    Returns ``"frontend"``, ``"backend"``, or ``"none"``. A request that hits
    both lexicons (or neither) is ``"none"`` — we only steer when the lean is
    unambiguous, so a mixed request competes flat instead of being mis-steered.
    """

    front = bool(keywords & _FRONTEND_INTENT)
    back = bool(keywords & _BACKEND_INTENT)
    if front and not back:
        return "frontend"
    if back and not front:
        return "backend"
    return "none"


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
