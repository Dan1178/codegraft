"""Repo-internal import-edge resolution — the lightweight reference scan.

Extracted from ``repo/rank.py`` so the same resolver backs both the ranking
import-edge signal *and* the on-demand reverse-dependency queries
(``impact_of`` / ``affected_tests``). It is deliberately a **heuristic reference
scan, not an AST**: JS/TS relative and ``@/`` alias specifiers resolve precisely;
bare packages and Python dotted modules fall back to an *unambiguous* basename
match. It misses dynamic imports, re-exports, and ambiguous basenames by design —
callers stamp their results ``resolution: "heuristic"`` accordingly.

The public surface is :func:`build_import_graph`, which turns a scan into a
forward/reverse edge map. ``rank.py`` re-imports the private helpers so its
``imported_by`` signal is byte-for-byte unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from codegraft.config import Config
from codegraft.models.repo import RepoScan

# Import extraction for the import-edge signal. JS/TS: any module string after
# `from` / `import` / `require(`. Python: `from a.b import c, d` / `import a.b`.
_JS_IMPORT_RE = re.compile(r"""(?:from|import|require)\s*\(?\s*['"]([^'"\n]+)['"]""")
_PY_FROM_RE = re.compile(r"^\s*from\s+([.\w]+)\s+import\s+(.+)$", re.MULTILINE)
_PY_IMPORT_RE = re.compile(r"^\s*import\s+([.\w][.\w\s,]*)", re.MULTILINE)

_JS_EXTS = {"ts", "tsx", "js", "jsx", "mjs", "cjs"}
# Extensions tried (in order) when resolving a JS/TS module specifier to a file.
# Leading "" lets an already-suffixed specifier resolve as-is.
_RESOLVE_EXTS = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".d.ts")


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _build_path_index(files) -> tuple[set[str], dict[str, list[str]]]:
    """Index candidate files for import resolution: the full path set plus a
    basename-stem → paths map used as a last-resort match for bare/dotted imports."""

    all_paths = {f.path for f in files}
    by_basename: dict[str, list[str]] = {}
    for path in all_paths:
        stem = _basename(path).rsplit(".", 1)[0]
        by_basename.setdefault(stem, []).append(path)
    return all_paths, by_basename


def _normalize_rel(importer: str, spec: str) -> str:
    """Resolve a relative specifier (``./x``, ``../y/z``) against the importer's
    directory into a repo-relative, slash-joined base path (no extension)."""

    parts = importer.split("/")[:-1]  # importer's directory
    for seg in spec.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def _match_module(base: str, all_paths: set[str]) -> str | None:
    """Map a module base path to a real candidate file, trying source extensions
    and an ``index`` barrel — the way a JS/TS resolver would."""

    for ext in _RESOLVE_EXTS:
        if (cand := base + ext) in all_paths:
            return cand
    for ext in _RESOLVE_EXTS[1:]:
        if (cand := f"{base}/index{ext}") in all_paths:
            return cand
    return None


def _resolve_specifier(spec: str, importer: str, all_paths: set[str]) -> str | None:
    """Resolve a JS/TS import specifier to a candidate path, precisely. Relative
    and ``@/`` (→ ``src/``) specifiers resolve by path; bare package imports don't."""

    if spec.startswith("."):
        return _match_module(_normalize_rel(importer, spec), all_paths)
    if spec.startswith("@/"):
        return _match_module("src/" + spec[2:], all_paths)
    return None


def _referenced_paths(
    text: str, importer: str, all_paths: set[str], by_basename: dict[str, list[str]]
) -> set[str]:
    """Repo-internal files that *importer* imports.

    Precise for JS/TS relative/alias specifiers; for bare packages and Python
    dotted modules it falls back to a basename match, but only when that basename
    is unambiguous — an ambiguous match would smear the centrality boost across
    same-named files in different directories.
    """

    ext = importer.rsplit(".", 1)[-1].lower() if "." in importer else ""
    refs: set[str] = set()
    bare: set[str] = set()

    if ext in _JS_EXTS:
        for spec in _JS_IMPORT_RE.findall(text):
            resolved = _resolve_specifier(spec, importer, all_paths)
            if resolved:
                refs.add(resolved)
            else:
                bare.add(spec.rsplit("/", 1)[-1])
    elif ext == "py":
        for module, names in _PY_FROM_RE.findall(text):
            bare.add(module.strip(".").rsplit(".", 1)[-1])
            for name in names.split(","):
                token = name.strip().split(" ")[0].strip("()")  # drop `as alias`
                if token and token != "*":
                    bare.add(token)
        for group in _PY_IMPORT_RE.findall(text):
            for module in group.split(","):
                token = module.strip().split(" ")[0]
                if token:
                    bare.add(token.rsplit(".", 1)[-1])
    else:
        return refs

    for token in bare:
        stem = token.rsplit(".", 1)[0]
        paths = by_basename.get(stem)
        if paths and len(paths) == 1 and paths[0] != importer:
            refs.add(paths[0])

    refs.discard(importer)
    return refs


def _read_head(abs_path: Path, max_lines: int) -> str | None:
    """Read the first *max_lines* lines of a file, or None if it can't be read."""

    try:
        with abs_path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = []
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                lines.append(line)
            return "".join(lines)
    except OSError:
        return None


@dataclass
class ImportGraph:
    """Repo-internal import edges, both directions.

    ``forward[path]`` is the set of repo files *path* imports; ``reverse[path]``
    is the set of files that import *path* (the transpose). Both are derived from
    the same heuristic reference scan, so neither is a correctness oracle — see
    the module docstring for the known blind spots.
    """

    forward: dict[str, set[str]] = field(default_factory=dict)
    reverse: dict[str, set[str]] = field(default_factory=dict)
    by_basename: dict[str, list[str]] = field(default_factory=dict)

    def importers_of(self, path: str) -> set[str]:
        """Files that directly import *path* (empty set if none/unknown)."""

        return self.reverse.get(path, set())

    def imports_of(self, path: str) -> set[str]:
        """Repo files that *path* directly imports (empty set if none/unknown)."""

        return self.forward.get(path, set())


def build_import_graph(scan: RepoScan, root: Path, config: Config) -> ImportGraph:
    """Build the forward/reverse import-edge map over **all** scan candidates.

    Reads each candidate's head once (bounded by ``config.repo.max_file_lines``)
    and resolves references with the shared heuristic helpers. This is
    O(candidates) head-reads — heavier than ranking's stage-2 subset — so it is
    meant for on-demand queries, not a background index. The candidate list is
    already bounded by ``max_candidate_files`` (``scan.truncated`` flags the cut),
    so a huge repo degrades predictably rather than stalling.
    """

    all_paths, by_basename = _build_path_index(scan.files)
    forward: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    max_lines = config.repo.max_file_lines

    for f in scan.files:
        text = _read_head(root / f.path, max_lines)
        if text is None:
            continue
        refs = _referenced_paths(text, f.path, all_paths, by_basename)
        if not refs:
            continue
        forward[f.path] = refs
        for ref in refs:
            reverse.setdefault(ref, set()).add(f.path)

    return ImportGraph(forward=forward, reverse=reverse, by_basename=by_basename)
