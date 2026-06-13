"""Ranking sanity tests against a small FastAPI-style fixture repo."""

from __future__ import annotations

from pathlib import Path

from codegraft.config import Config
from codegraft.repo.analyze import analyze_repo
from codegraft.repo.rank import rank_files
from codegraft.repo.summarize import summarize
from codegraft.repo.discover import discover_repo
from tests.conftest import write


def _fixture_repo(root: Path) -> None:
    write(root, "pyproject.toml", '[project]\ndependencies = ["fastapi", "sqlalchemy"]\n')
    write(root, "README.md", "# Demo service\nA small API.\n")
    write(
        root,
        "app/routes/admin.py",
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/admin')\n"
        "def admin_panel(role):\n"
        "    # restrict admin access by role\n"
        "    return check_role(role)\n",
    )
    write(
        root,
        "app/routes/health.py",
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok'}\n",
    )
    write(
        root,
        "app/services/auth.py",
        "def check_access(user, role):\n"
        "    # role-based access control logic\n"
        "    return user.role == role\n",
    )
    write(
        root,
        "app/models/user.py",
        "class User:\n    def __init__(self, role):\n        self.role = role\n",
    )
    write(root, "app/db.py", "ENGINE = 'sqlite://'\n")


def _config(root: Path) -> Config:
    config = Config.load(root)
    config.repo.prefer_git_ls_files = False  # deterministic filesystem scan
    return config


def _analysis(root: Path):
    return analyze_repo("add role-based access control to admin routes", root, _config(root))


def test_relevant_files_rank_near_top(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    ranked = _analysis(tmp_path).ranked
    paths = [r.path for r in ranked]

    assert paths, "expected some ranked files"
    # The admin route, auth service, and user model are all clearly relevant.
    top3 = set(paths[:3])
    assert "app/routes/admin.py" in top3
    assert top3 & {"app/services/auth.py", "app/models/user.py"}


def test_relevant_outranks_irrelevant(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    ranked = {r.path: r.score for r in _analysis(tmp_path).ranked}

    # admin.py (filename + role + content hits) should beat health.py (route only)
    # and db.py (no keyword signal at all).
    assert ranked["app/routes/admin.py"] > ranked.get("app/routes/health.py", 0)
    assert ranked["app/routes/admin.py"] > ranked.get("app/db.py", 0)


def test_signals_are_explainable(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    ranked = {r.path: r for r in _analysis(tmp_path).ranked}
    admin = ranked["app/routes/admin.py"]
    # The score must be decomposable — that's the anti-black-box guarantee.
    assert admin.signals
    assert abs(sum(admin.signals.values()) - admin.score) < 1e-6


def test_empty_request_ranks_nothing(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    config = _config(tmp_path)
    scan = discover_repo(tmp_path, config)
    summary = summarize(scan)
    assert rank_files("", scan, summary, config) == []
    assert rank_files("add the", scan, summary, config) == []  # all stopwords


def test_max_ranked_files_cap(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    config = _config(tmp_path)
    config.analysis.max_ranked_files = 2
    scan = discover_repo(tmp_path, config)
    summary = summarize(scan)
    ranked = rank_files("role access admin routes user", scan, summary, config)
    assert len(ranked) <= 2


def test_content_only_file_is_ranked(tmp_path: Path) -> None:
    """A file relevant only by its *content* (no path/name keyword) still ranks.

    Regression: stage 1 used to drop zero-path-score files before content was
    read, so content-only matches were invisible.
    """

    write(tmp_path, "pyproject.toml", "[project]\n")
    # No keyword in the path or filename — only in the body.
    write(tmp_path, "lib/helpers.py", "def do():\n    # handles access by role\n    return True\n")
    write(tmp_path, "lib/unrelated.py", "def noop():\n    return None\n")

    ranked = {r.path for r in analyze_repo("role access", tmp_path, _config(tmp_path)).ranked}
    assert "lib/helpers.py" in ranked


def test_doc_code_blocks_do_not_score_as_symbols(tmp_path: Path) -> None:
    """A class/def inside a markdown code block must not earn a symbol signal.

    Regression: the symbol regex matched code fences in README/blueprint docs,
    letting a large doc outrank real source.
    """

    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "notes.md", "Design:\n```python\nclass AccessRole:\n    pass\n```\n")
    write(tmp_path, "svc/access.py", "class AccessRole:\n    role = 1\n")

    ranked = {r.path: r for r in analyze_repo("access role", tmp_path, _config(tmp_path)).ranked}
    assert "notes.md" not in ranked or "symbol" not in ranked["notes.md"].signals
    # The real source file must win.
    assert ranked["svc/access.py"].score > ranked.get("notes.md", ranked["svc/access.py"]).score \
        or "notes.md" not in ranked


def _taxonomy_repo(root: Path) -> None:
    """A repo where three thin, keyword-named screens all delegate to one shared
    screen whose own name carries no request keyword — the meshimate topology."""

    write(root, "package.json", '{"dependencies": {"react": "*"}}\n')
    for noun in ("Categories", "Tags", "Components"):
        write(
            root,
            f"src/features/taxonomy/screens/{noun}Screen.tsx",
            "import { TaxonomyManagementScreen } from './TaxonomyManagementScreen';\n"
            f"export function {noun}Screen() {{\n"
            f"  return <TaxonomyManagementScreen title=\"{noun}\" />;\n"
            "}\n",
        )
    # The shared implementation: keyword-poor name, generic body. On filename and
    # content alone it loses to its own wrappers and eats a diversity penalty for
    # sharing their directory — exactly the file that used to fall out.
    write(
        root,
        "src/features/taxonomy/screens/TaxonomyManagementScreen.tsx",
        "export function TaxonomyManagementScreen({ title }) {\n"
        "  // Shared list: rename and remove rows.\n"
        "  return null;\n"
        "}\n",
    )
    write(root, "src/lib/theme.ts", "export const colors = {};\n")


def test_imported_central_file_is_pulled_in(tmp_path: Path) -> None:
    """A shared file imported by several relevant files earns the import-edge
    signal and surfaces, even though its name matches no request keyword."""

    _taxonomy_repo(tmp_path)
    request = "add categories, tags, and components from the settings screen"
    ranked = {r.path: r for r in analyze_repo(request, tmp_path, _config(tmp_path)).ranked}

    shared = "src/features/taxonomy/screens/TaxonomyManagementScreen.tsx"
    assert shared in ranked, "shared screen should be pulled in by its importers"
    signals = ranked[shared].signals
    # Imported by all three wrappers (within the ubiquity gate): 3 * W_IMPORTED_BY.
    assert signals.get("imported_by") == 4.5
    # The new signal still obeys the explainability invariant.
    assert abs(sum(signals.values()) - ranked[shared].score) < 1e-6


def test_import_edge_can_be_disabled(tmp_path: Path) -> None:
    """The ablation toggle removes the signal entirely (eval --no-import-edge)."""

    _taxonomy_repo(tmp_path)
    config = _config(tmp_path)
    config.analysis.use_import_edge = False
    request = "add categories, tags, and components from the settings screen"
    ranked = analyze_repo(request, tmp_path, config).ranked

    assert all("imported_by" not in r.signals for r in ranked)


def test_summary_detects_stack(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    summary = _analysis(tmp_path).summary
    assert summary.primary_language == "Python"
    assert "FastAPI" in summary.frameworks
    assert "pyproject.toml" in summary.manifests
