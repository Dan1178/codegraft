"""Filesystem-walk fallback discovery with ``.gitignore`` semantics.

Used only when git is unavailable or the target is not a git repo. We replicate
gitignore behaviour with PathSpec's ``GitIgnoreSpec``, including *nested*
``.gitignore`` files: patterns in ``a/.gitignore`` apply only to paths under
``a/``.

Known limitation vs. real git: cross-file negation (a ``!pattern`` in a deeper
``.gitignore`` re-including something ignored by a shallower one) is not modelled
— a path is ignored if *any* applicable spec matches. This is acceptable because
git is the primary path; this fallback only runs when git is absent.
"""

from __future__ import annotations

import os
from pathlib import Path

from pathspec import GitIgnoreSpec

GITIGNORE = ".gitignore"


def _posix_rel(path: Path, root: Path) -> str:
    """Repo-relative, forward-slash path."""

    return path.relative_to(root).as_posix()


class _IgnoreIndex:
    """Per-directory ``GitIgnoreSpec`` index keyed by posix dir path ("" = root)."""

    def __init__(self) -> None:
        self._specs: dict[str, GitIgnoreSpec] = {}

    def add_dir(self, dir_key: str, gitignore_path: Path) -> None:
        lines = gitignore_path.read_text(encoding="utf-8", errors="replace").splitlines()
        self._specs[dir_key] = GitIgnoreSpec.from_lines(lines)

    def is_ignored(self, rel_posix: str, is_dir: bool) -> bool:
        """Check a path against every ancestor directory's spec."""

        candidate = rel_posix + "/" if is_dir else rel_posix
        for dir_key, spec in self._specs.items():
            if dir_key == "":
                scoped = candidate
            elif rel_posix == dir_key or rel_posix.startswith(dir_key + "/"):
                scoped = candidate[len(dir_key) + 1:]
            else:
                continue  # spec doesn't govern this path
            if scoped and spec.match_file(scoped):
                return True
        return False


def filesystem_scan(root: Path, respect_gitignore: bool = True) -> set[str]:
    """Walk *root* and return repo-relative paths, honouring nested ``.gitignore``.

    Always skips the ``.git`` directory. Directories that are ignored are pruned
    so we never descend into them.
    """

    index = _IgnoreIndex()
    results: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dir_key = "" if current == root else _posix_rel(current, root)

        # Load this directory's .gitignore before evaluating its children.
        if respect_gitignore and GITIGNORE in filenames:
            index.add_dir(dir_key, current / GITIGNORE)

        # Prune subdirectories in place so os.walk won't descend into them.
        kept_dirs = []
        for name in dirnames:
            if name == ".git":
                continue
            child_rel = _posix_rel(current / name, root)
            if respect_gitignore and index.is_ignored(child_rel, is_dir=True):
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for name in filenames:
            file_rel = _posix_rel(current / name, root)
            if respect_gitignore and index.is_ignored(file_rel, is_dir=False):
                continue
            results.add(file_rel)

    return results
