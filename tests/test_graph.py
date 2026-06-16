"""Tests for the reverse-dependency query layer (impact_of / affected_tests).

These exercise the transpose of the import scan extracted in repo/imports.py.
The refactor guard — that repo/rank.py's import-edge behaviour is unchanged — is
test_rank.py's existing import-edge tests, which stay green byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path

from codegraft.config import Config
from codegraft.repo.discover import discover_repo
from codegraft.repo.graph import affected_tests, impact_of, resolve_target
from codegraft.repo.summarize import summarize
from tests.conftest import write


def _config(root: Path) -> Config:
    config = Config.load(root)
    config.repo.prefer_git_ls_files = False  # deterministic filesystem scan
    return config


def _scan(root: Path):
    config = _config(root)
    return discover_repo(root, config), config


def _taxonomy_repo(root: Path) -> None:
    """Three thin wrappers (JS relative imports) all importing one shared screen."""

    write(root, "package.json", '{"dependencies": {"react": "*"}}\n')
    for noun in ("Categories", "Tags", "Components"):
        write(
            root,
            f"src/features/taxonomy/screens/{noun}Screen.tsx",
            "import { TaxonomyManagementScreen } from './TaxonomyManagementScreen';\n"
            f"export function {noun}Screen() {{ return <TaxonomyManagementScreen />; }}\n",
        )
    write(
        root,
        "src/features/taxonomy/screens/TaxonomyManagementScreen.tsx",
        "export function TaxonomyManagementScreen() { return null; }\n",
    )
    write(root, "src/lib/theme.ts", "export const colors = {};\n")


def test_impact_of_inverts_js_relative_edges(tmp_path: Path) -> None:
    """The shared screen's importers are exactly the three wrappers that import it."""

    _taxonomy_repo(tmp_path)
    scan, config = _scan(tmp_path)
    shared = "src/features/taxonomy/screens/TaxonomyManagementScreen.tsx"

    result = impact_of(shared, scan, tmp_path, config)

    assert result.found and result.resolved == shared
    assert result.imported_by == sorted(
        f"src/features/taxonomy/screens/{n}Screen.tsx"
        for n in ("Categories", "Tags", "Components")
    )
    assert result.resolution == "heuristic"


def test_impact_of_inverts_python_from_import(tmp_path: Path) -> None:
    """`from a.b import c` edges invert: shared.py's importers are its dependents."""

    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "app/shared.py", "def helper():\n    return 1\n")
    write(tmp_path, "app/one.py", "from app.shared import helper\n")
    write(tmp_path, "app/two.py", "from app.shared import helper\n")
    write(tmp_path, "app/lonely.py", "VALUE = 1\n")
    scan, config = _scan(tmp_path)

    result = impact_of("app/shared.py", scan, tmp_path, config)

    assert result.imported_by == ["app/one.py", "app/two.py"]


def test_impact_of_resolves_bare_basename(tmp_path: Path) -> None:
    """A unique bare filename resolves to its full path."""

    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "app/shared.py", "def helper():\n    return 1\n")
    write(tmp_path, "app/one.py", "from app.shared import helper\n")
    scan, config = _scan(tmp_path)

    result = impact_of("shared.py", scan, tmp_path, config)

    assert result.resolved == "app/shared.py"
    assert result.imported_by == ["app/one.py"]


def test_impact_of_leaf_file_is_empty_not_error(tmp_path: Path) -> None:
    """A file nobody imports yields an empty list, not an error."""

    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "app/lonely.py", "VALUE = 1\n")
    scan, config = _scan(tmp_path)

    result = impact_of("app/lonely.py", scan, tmp_path, config)

    assert result.found
    assert result.imported_by == []


def test_impact_of_ambiguous_basename_does_not_smear(tmp_path: Path) -> None:
    """An ambiguous bare basename resolves to nothing and lists the candidates,
    rather than smearing importers across same-named files."""

    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "a/models.py", "X = 1\n")
    write(tmp_path, "b/models.py", "Y = 2\n")
    write(tmp_path, "a/use.py", "from a.models import X\n")
    scan, config = _scan(tmp_path)

    result = impact_of("models.py", scan, tmp_path, config)

    assert not result.found
    assert result.imported_by == []
    assert result.ambiguous == ["a/models.py", "b/models.py"]


def test_impact_of_unknown_target(tmp_path: Path) -> None:
    """A target matching no candidate is not found and has no candidates."""

    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "app/real.py", "X = 1\n")
    scan, config = _scan(tmp_path)

    result = impact_of("nope.py", scan, tmp_path, config)

    assert not result.found
    assert result.ambiguous == []


def test_impact_of_transitive_closure(tmp_path: Path) -> None:
    """`transitive=True` reaches importers-of-importers, beyond the direct set."""

    # Names are kept distinct from module basenames so the heuristic basename
    # fallback doesn't make `top` resolve straight to `base` — we want a real chain.
    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "app/base.py", "def base_fn():\n    return 1\n")
    write(tmp_path, "app/mid.py", "from app.base import base_fn\n")
    write(tmp_path, "app/top.py", "from app.mid import mid_thing\n")
    scan, config = _scan(tmp_path)

    result = impact_of("app/base.py", scan, tmp_path, config, transitive=True)

    assert result.imported_by == ["app/mid.py"]      # direct only
    assert result.transitive == ["app/top.py"]       # one hop further


def test_resolve_target_path_suffix(tmp_path: Path) -> None:
    """A path suffix resolves even when the repo is rooted elsewhere."""

    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "static/css/style.css", ".a { color: red; }\n")
    scan, _config_ = _scan(tmp_path)

    resolved, candidates = resolve_target("css/style.css", scan)

    assert resolved == "static/css/style.css"
    assert candidates == []


# --- Plan C: affected_tests (test-impact selection) ---


def _tested_repo(root: Path) -> None:
    """A module imported (transitively) by a test, plus an unrelated test."""

    write(root, "pyproject.toml", "[project]\n")
    write(root, "app/core.py", "def core():\n    return 1\n")
    write(root, "app/feature.py", "from app.core import core\n")
    write(root, "tests/test_feature.py", "from app.feature import core\ndef test_it():\n    pass\n")
    write(root, "tests/test_other.py", "def test_other():\n    pass\n")


def test_affected_tests_selects_transitive_dependent(tmp_path: Path) -> None:
    """A test importing a module that imports the changed file is selected
    (proves the closure is transitive, not just direct importers)."""

    _tested_repo(tmp_path)
    scan, config = _scan(tmp_path)
    summary = summarize(scan)

    result = affected_tests(["app/core.py"], scan, summary, tmp_path, config)

    assert result.tests == ["tests/test_feature.py"]
    assert "tests/test_other.py" not in result.tests
    assert result.completeness == "heuristic"


def test_affected_tests_no_dependents_is_empty(tmp_path: Path) -> None:
    """A changed file with no dependent tests yields an empty list, not an error."""

    _tested_repo(tmp_path)
    scan, config = _scan(tmp_path)
    summary = summarize(scan)

    write(tmp_path, "app/orphan.py", "Z = 1\n")
    scan, config = _scan(tmp_path)
    summary = summarize(scan)

    result = affected_tests(["app/orphan.py"], scan, summary, tmp_path, config)

    assert result.tests == []


def test_affected_tests_editing_a_test_selects_it(tmp_path: Path) -> None:
    """Editing a test file selects that test itself."""

    _tested_repo(tmp_path)
    scan, config = _scan(tmp_path)
    summary = summarize(scan)

    result = affected_tests(["tests/test_other.py"], scan, summary, tmp_path, config)

    assert "tests/test_other.py" in result.tests


def test_affected_tests_reports_unresolved(tmp_path: Path) -> None:
    """A changed input not present in the scan is reported, not silently dropped."""

    _tested_repo(tmp_path)
    scan, config = _scan(tmp_path)
    summary = summarize(scan)

    result = affected_tests(["app/core.py", "ghost.py"], scan, summary, tmp_path, config)

    assert result.unresolved == ["ghost.py"]
    assert result.tests == ["tests/test_feature.py"]
