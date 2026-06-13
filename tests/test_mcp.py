"""Tests for the MCP server adapter.

The payload builders hold the logic and need no `mcp` SDK; the server build is
smoke-tested and skipped if the optional dependency is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codegraft.mcp import select_context_payload
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


def test_build_server_registers_tools() -> None:
    pytest.importorskip("mcp")
    from codegraft.mcp import build_server

    server = build_server()
    assert server is not None  # constructs without error with the SDK present
