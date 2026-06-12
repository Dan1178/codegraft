"""Tests for language/manifest/entry-point detection and tree rendering."""

from __future__ import annotations

from codegraft.repo import detect
from codegraft.repo.tree import build_tree


def test_language_mix_counts_code_only() -> None:
    paths = ["app/main.py", "app/util.py", "web/index.ts", "README.md", "data.json"]
    mix = detect.language_mix(paths)
    assert mix["Python"] == 2
    assert mix["TypeScript"] == 1
    assert "Markdown" not in mix  # docs/config excluded from the mix
    assert detect.primary_language(mix) == "Python"


def test_manifests_prefer_shallow() -> None:
    paths = ["sub/pyproject.toml", "pyproject.toml", "app/models.py"]
    manifests = detect.find_manifests(paths)
    assert manifests[0] == "pyproject.toml"  # root before nested


def test_entry_points_and_tests() -> None:
    paths = ["app/main.py", "tests/test_x.py", "pkg/util.py"]
    assert "app/main.py" in detect.find_entry_points(paths)
    assert "tests" in detect.find_test_paths(paths)


def test_build_tree_depth_and_width() -> None:
    paths = [f"src/pkg/mod{i}.py" for i in range(30)]
    tree = build_tree(paths, max_depth=2, max_entries=20)
    assert "src/" in tree
    assert "pkg/" in tree
    # Depth limit collapses deeper contents into an entry-count hint.
    assert "entries" in tree or "more" in tree
