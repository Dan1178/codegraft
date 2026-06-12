"""Deterministic relevant-file ranking.

This is the heart of codegraft: given a feature request and a scanned repo,
decide which files are worth showing the planning model. It is intentionally an
explainable heuristic, not an LLM call or an embedding lookup — every file
carries a `signals` breakdown so weak ranking is debuggable via `inspect`.

Two stages keep file I/O bounded on large repos:
  1. Cheap pass over *all* candidates using path/role/structure signals only.
  2. Read content for the top `stage2_limit` files and add content-keyword and
     symbol-overlap signals, then re-rank.

A final diversity penalty stops one directory from dominating the results.
"""

from __future__ import annotations

import re
from pathlib import Path

from codegraft.config import Config
from codegraft.models.repo import RankedFile, RepoScan, RepoSummary
from codegraft.repo import detect
from codegraft.utils.text import extract_keywords, split_identifier, tokenize

# Languages whose files carry meaningful def/class symbols. Docs and data files
# (Markdown, JSON, TOML, ...) are excluded so code blocks inside a README or the
# project blueprint don't get scored as if they were real source symbols.
_NON_CODE_LANGS = {"Markdown", "JSON", "YAML", "TOML", "HTML", "CSS", "Text"}


def _is_code(path: str) -> bool:
    lang = detect.language_of(path)
    return lang is not None and lang not in _NON_CODE_LANGS

# --- Scoring weights (tunable). Kept as named constants so `inspect` output can
# be read against them while tuning. ---
W_FILENAME_HIT = 6.0     # a keyword appears in the file's own name
W_PATH_HIT = 3.0         # a keyword appears elsewhere in the path
W_ROLE = 1.0             # multiplier applied to per-role weights below
W_ENTRY = 2.0            # file is an application entry point
W_MANIFEST = 1.5         # root/build manifest (always mildly relevant)
W_TEST = 1.5             # test file, when the request looks test-related
W_CONTENT_HIT = 0.4      # per keyword occurrence in content (capped)
CONTENT_HIT_CAP = 12     # don't let one huge file dominate on raw counts
W_SYMBOL = 4.0           # per keyword matching a defined symbol name
ROOT_PROXIMITY = 1.0     # shallow files are slightly more likely to matter
DIVERSITY_PENALTY = 1.5  # subtracted per already-selected file in same dir...
DIVERSITY_PENALTY_CAP = 3  # ...but capped, so a single-folder scope isn't crushed

# Architectural role hints keyed by path segment.
_ROLE_WEIGHTS: dict[str, float] = {
    "routes": 3.0, "route": 3.0, "router": 3.0, "controllers": 3.0,
    "controller": 3.0, "handlers": 3.0, "handler": 3.0, "endpoints": 3.0,
    "endpoint": 3.0, "api": 2.5, "views": 2.5, "view": 2.5,
    "services": 2.5, "service": 2.5, "usecases": 2.5, "use_cases": 2.5,
    "domain": 2.0, "models": 2.5, "model": 2.5, "schemas": 2.5, "schema": 2.5,
    "migrations": 2.5, "migration": 2.5, "entities": 2.0, "middleware": 2.0,
    "auth": 2.5, "core": 1.5,
}

_TEST_REQUEST_TOKENS = {"test", "tests", "testing", "coverage", "regression"}

_SYMBOL_RE = re.compile(
    r"\b(?:def|class|func|function|type|struct|interface|fn|const|var)\s+([A-Za-z_]\w*)"
)

# How many files to read content for, per scale mode.
_STAGE2_LIMIT = {"normal": 50, "medium": 35, "large": 20}


def _mode_cap(config: Config, mode: str) -> int:
    base = config.analysis.max_ranked_files
    if mode == "large":
        return min(base, 6)
    if mode == "medium":
        return min(base, 10)
    return base


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _stage1_signals(
    path: str, keywords: set[str], summary: RepoSummary, request_is_testy: bool
) -> dict[str, float]:
    """Path/structure-only signals — no file read."""

    signals: dict[str, float] = {}
    segments = path.split("/")
    name = segments[-1]
    name_tokens = set(tokenize(name))
    path_tokens = set(tokenize("/".join(segments[:-1])))

    filename_hits = len(keywords & name_tokens)
    if filename_hits:
        signals["filename"] = filename_hits * W_FILENAME_HIT
    path_hits = len(keywords & path_tokens)
    if path_hits:
        signals["path"] = path_hits * W_PATH_HIT

    role = sum(_ROLE_WEIGHTS.get(seg.lower(), 0.0) for seg in segments)
    if role:
        signals["role"] = role * W_ROLE

    if path in summary.entry_points:
        signals["entry_point"] = W_ENTRY
    if _basename(path) in {_basename(m) for m in summary.manifests}:
        signals["manifest"] = W_MANIFEST

    is_test = path in summary.test_paths or any(
        path.startswith(t + "/") or path == t for t in summary.test_paths
    )
    if is_test and request_is_testy:
        signals["test"] = W_TEST

    # Shallow files get a small nudge (entry points and core config live near root).
    depth = path.count("/")
    if depth <= 1:
        signals["proximity"] = ROOT_PROXIMITY

    return signals


def _stage2_signals(
    rel_path: str, abs_path: Path, keywords: set[str], max_lines: int
) -> dict[str, float]:
    """Content-keyword and symbol-overlap signals — reads the file (bounded)."""

    try:
        with abs_path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = []
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                lines.append(line)
            text = "".join(lines)
    except OSError:
        return {}

    signals: dict[str, float] = {}

    content_tokens = tokenize(text)
    hits = sum(1 for tok in content_tokens if tok in keywords)
    if hits:
        signals["content"] = min(hits, CONTENT_HIT_CAP) * W_CONTENT_HIT

    # Only score symbols in actual source files — not code blocks inside docs.
    if _is_code(rel_path):
        symbol_tokens: set[str] = set()
        for match in _SYMBOL_RE.finditer(text):
            symbol_tokens.update(split_identifier(match.group(1)))
        symbol_overlap = len(keywords & symbol_tokens)
        if symbol_overlap:
            signals["symbol"] = symbol_overlap * W_SYMBOL

    return signals


def rank_files(
    request: str, scan: RepoScan, summary: RepoSummary, config: Config
) -> list[RankedFile]:
    """Return the top relevant files for *request*, scored and explained."""

    keywords = extract_keywords(request)
    if not keywords:
        return []

    request_is_testy = bool(keywords & _TEST_REQUEST_TOKENS)
    root = Path(scan.root)

    # Stage 1: cheap path-based scoring over *every* candidate. We keep files
    # with a zero path score too — many relevant files (e.g. a config module
    # that only mentions the keyword in its body) match on content alone, so
    # dropping them here would prevent them from ever being read in stage 2.
    stage1: list[RankedFile] = []
    for f in scan.files:
        signals = _stage1_signals(f.path, keywords, summary, request_is_testy)
        stage1.append(RankedFile(path=f.path, score=sum(signals.values()), signals=signals))

    stage1.sort(key=lambda r: (-r.score, r.path))

    # Stage 2: read content for the strongest path-level candidates. On large
    # repos this bounds I/O; content-only files past the cutoff keep their
    # (path-only) score, which is the documented large-repo tradeoff.
    stage2_limit = _STAGE2_LIMIT.get(summary.mode, 50)
    for ranked in stage1[:stage2_limit]:
        extra = _stage2_signals(
            ranked.path, root / ranked.path, keywords, config.repo.max_file_lines
        )
        if extra:
            ranked.signals.update(extra)
            ranked.score += sum(extra.values())

    # Now drop files with no signal at all and re-rank.
    stage1 = [r for r in stage1 if r.score > 0]
    stage1.sort(key=lambda r: (-r.score, r.path))

    # Diversity penalty + final cut: discourage one *folder* from dominating.
    # Key on the immediate parent directory, not the top-level segment — in a
    # src/-layout repo the whole source tree shares one top segment, so keying
    # on it would wrongly penalize all real code relative to scattered root docs.
    cap = _mode_cap(config, summary.mode)
    selected: list[RankedFile] = []
    dir_counts: dict[str, int] = {}
    for ranked in stage1:
        parent = ranked.path.rsplit("/", 1)[0] if "/" in ranked.path else ""
        penalty = min(dir_counts.get(parent, 0), DIVERSITY_PENALTY_CAP) * DIVERSITY_PENALTY
        if penalty:
            ranked.signals["diversity_penalty"] = -penalty
            ranked.score -= penalty
        selected.append(ranked)
        dir_counts[parent] = dir_counts.get(parent, 0) + 1

    selected.sort(key=lambda r: (-r.score, r.path))
    return selected[:cap]
