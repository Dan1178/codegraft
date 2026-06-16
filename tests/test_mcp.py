"""Tests for the MCP server adapter.

The payload builders hold the logic and need no `mcp` SDK; the server build is
smoke-tested and skipped if the optional dependency is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codegraft.mcp import (
    affected_tests_payload,
    get_symbol_payload,
    impact_of_payload,
    select_context_payload,
)
from tests.conftest import write


def _fixture(root: Path) -> None:
    write(root, "pyproject.toml", '[project]\ndependencies = ["fastapi"]\n')
    write(
        root,
        "app/routes/admin.py",
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
        "def admin(role):\n    return role\n",
    )
    write(root, "app/util.py", "x = 1\n")


def test_select_context_payload_shape(tmp_path: Path) -> None:
    _fixture(tmp_path)
    payload = select_context_payload("add role-based access to admin routes", str(tmp_path))

    assert payload["repo_root"]
    assert payload["summary"]["primary_language"] == "Python"
    assert isinstance(payload["ranked_files"], list) and payload["ranked_files"]
    # Ranked entries carry the explainable signal breakdown.
    assert "signals" in payload["ranked_files"][0]
    assert "snippets" in payload and "token_estimate" in payload
    assert payload["token_estimate"]["saved_tokens"] >= 0


def test_select_context_is_json_serializable(tmp_path: Path) -> None:
    import json

    _fixture(tmp_path)
    payload = select_context_payload("admin role", str(tmp_path))
    json.dumps(payload)  # must not raise


def _graph_fixture(root: Path) -> None:
    # Imported names are kept distinct from module basenames so the heuristic
    # basename fallback resolves a real chain (core <- feature <- test), not a
    # shortcut from the test straight to core.
    write(root, "pyproject.toml", "[project]\n")
    write(root, "app/core.py", "def core_fn():\n    return 1\n")
    write(root, "app/feature.py", "from app.core import core_fn\n")
    write(root, "tests/test_feature.py", "from app.feature import feature_fn\ndef test_it():\n    pass\n")


def test_impact_of_payload_shape(tmp_path: Path) -> None:
    import json

    _graph_fixture(tmp_path)
    # filesystem scan is fine; the repo has no .git so discover falls back.
    payload = impact_of_payload("app/core.py", str(tmp_path))

    assert payload["resolved"] == "app/core.py"
    assert payload["imported_by"] == ["app/feature.py"]
    assert payload["resolution"] == "heuristic"
    json.dumps(payload)  # must be JSON-serializable


def test_impact_of_payload_transitive(tmp_path: Path) -> None:
    _graph_fixture(tmp_path)
    payload = impact_of_payload("app/core.py", str(tmp_path), transitive=True)

    assert "transitive" in payload
    assert payload["transitive"] == ["tests/test_feature.py"]


def test_get_symbol_payload_shape(tmp_path: Path) -> None:
    import json

    _graph_fixture(tmp_path)
    payload = get_symbol_payload("core_fn", str(tmp_path))

    assert payload["name"] == "core_fn"
    assert payload["resolution"] == "heuristic"
    assert len(payload["matches"]) == 1
    match = payload["matches"][0]
    assert match["path"] == "app/core.py"
    assert match["signature"].startswith("def core_fn")
    assert match["span"] == [1, 2]
    json.dumps(payload)


def test_affected_tests_payload_shape(tmp_path: Path) -> None:
    import json

    _graph_fixture(tmp_path)
    payload = affected_tests_payload(["app/core.py"], str(tmp_path))

    assert payload["tests"] == ["tests/test_feature.py"]
    assert payload["completeness"] == "heuristic"
    json.dumps(payload)


def test_build_server_registers_tools() -> None:
    import asyncio

    pytest.importorskip("mcp")
    from codegraft.mcp import build_server

    server = build_server()
    assert server is not None  # constructs without error with the SDK present
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == {
        "select_context",
        "impact_of",
        "get_symbol",
        "affected_tests",
        "generate_plan",
    }
