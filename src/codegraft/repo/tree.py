"""Compact, depth-limited directory tree rendering.

A model doesn't need the whole tree — it needs enough shape to reason about
where things live. So we cap depth and the number of entries shown per
directory, summarizing the rest as a "… N more" line. Pure function of the
path list; no filesystem access.
"""

from __future__ import annotations

from typing import Any


def _insert(tree: dict[str, Any], parts: list[str]) -> None:
    node = tree
    for part in parts:
        node = node.setdefault(part, {})


def build_tree(paths: list[str], max_depth: int = 3, max_entries: int = 20) -> str:
    """Render *paths* (repo-relative, forward-slash) as a compact tree string."""

    root: dict[str, Any] = {}
    for path in paths:
        _insert(root, path.split("/"))

    lines: list[str] = []
    _render(root, prefix="", depth=0, max_depth=max_depth, max_entries=max_entries, out=lines)
    return "\n".join(lines)


def _render(
    node: dict[str, Any],
    prefix: str,
    depth: int,
    max_depth: int,
    max_entries: int,
    out: list[str],
) -> None:
    # Directories (have children) before files, each group sorted.
    dirs = sorted(k for k, v in node.items() if v)
    files = sorted(k for k, v in node.items() if not v)
    entries = dirs + files

    shown = entries[:max_entries]
    hidden = len(entries) - len(shown)

    for name in shown:
        is_dir = bool(node[name])
        label = f"{name}/" if is_dir else name
        out.append(f"{prefix}{label}")
        if is_dir:
            if depth + 1 >= max_depth:
                # Don't descend further; hint that there's more below.
                child_count = _count(node[name])
                if child_count:
                    out.append(f"{prefix}  … ({child_count} entries)")
            else:
                _render(
                    node[name],
                    prefix + "  ",
                    depth + 1,
                    max_depth,
                    max_entries,
                    out,
                )

    if hidden > 0:
        out.append(f"{prefix}… ({hidden} more)")


def _count(node: dict[str, Any]) -> int:
    """Total descendant entries under a node."""

    total = 0
    for child in node.values():
        total += 1 + _count(child)
    return total
