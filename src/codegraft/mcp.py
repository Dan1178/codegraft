"""codegraft as an MCP server — a thin adapter, like the CLI.

Exposes codegraft's engine to any MCP client (Claude Code, etc.) as tools:

- ``select_context``  — the deterministic context bundle: ranked files +
  bounded snippets for a feature request. **Free, no LLM call, no API key.**
  This is the differentiated part — hand an agent the right files instantly so
  it explores less.
- ``generate_plan``   — the full structured plan via an LLM provider. **Opt-in;
  costs tokens / needs a key.** Prefer ``select_context`` for context.

The ``mcp`` SDK is an optional dependency (``codegraft[mcp]``) imported lazily,
so importing this module — and unit-testing the payload builders below — never
requires it. The payload builders hold the logic; the tool wrappers are trivial.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codegraft.config import Config
from codegraft.repo.analyze import analyze_repo


def select_context_payload(
    request: str, repo: str = ".", subdir: str | None = None
) -> dict[str, Any]:
    """Deterministic context bundle for *request* against the repo at *repo*."""

    root = Path(repo)
    analysis = analyze_repo(request, root, Config.load(root), subdir=subdir)
    est = analysis.token_estimate()
    return {
        "repo_root": analysis.scan.root,
        "ranking_signal": analysis.ranking_signal,
        "summary": {
            "primary_language": analysis.summary.primary_language,
            "frameworks": analysis.summary.frameworks,
            "manifests": analysis.summary.manifests,
            "entry_points": analysis.summary.entry_points,
            "file_count": analysis.summary.file_count,
            "mode": analysis.summary.mode,
        },
        "ranked_files": [
            {"path": r.path, "score": round(r.score, 1), "signals": r.signals}
            for r in analysis.ranked
        ],
        "snippets": [
            {"path": s.path, "content": s.content, "truncated": s.truncated}
            for s in analysis.snippets
        ],
        "token_estimate": {
            "bundle_tokens": est.bundle_tokens,
            "baseline_tokens": est.baseline_tokens,
            "saved_tokens": est.saved_tokens,
            "saved_pct": round(est.saved_pct, 1),
        },
    }


def generate_plan_payload(
    request: str,
    repo: str = ".",
    provider: str | None = None,
    model: str | None = None,
    subdir: str | None = None,
) -> dict[str, Any]:
    """Full structured plan (LLM call) as a JSON-serializable dict."""

    from codegraft.planning.service import generate_plan

    root = Path(repo)
    config = Config.load(root)
    if provider:
        config.provider.name = provider
    if model:
        config.provider.model = model
    plan = generate_plan(request, root, config, subdir=subdir)
    return plan.model_dump(mode="json")


def build_server() -> Any:
    """Construct the FastMCP server with codegraft's tools registered."""

    from mcp.server.fastmcp import FastMCP

    server = FastMCP("codegraft")

    @server.tool()
    def select_context(
        request: str, repo: str = ".", subdir: str | None = None
    ) -> dict[str, Any]:
        """Rank the files relevant to a feature request in a local repo and return
        bounded code snippets — a deterministic context bundle. No LLM call, no API
        key, no per-request cost. Use this to get the right files for a coding task
        fast, then plan/implement from them. `repo` is a local path; optional
        `subdir` scopes a large repo."""

        return select_context_payload(request, repo, subdir)

    @server.tool()
    def generate_plan(
        request: str,
        repo: str = ".",
        provider: str | None = None,
        model: str | None = None,
        subdir: str | None = None,
    ) -> dict[str, Any]:
        """Generate a full structured implementation plan (impacted files, phases,
        risks, tests, handoff prompts) via an LLM provider. This costs tokens and
        needs a provider API key — prefer `select_context` for free context, and
        use this only when you want a reviewable plan artifact."""

        return generate_plan_payload(request, repo, provider, model, subdir)

    return server


def main() -> None:
    """Console entry point: run the server over stdio."""

    build_server().run()


if __name__ == "__main__":
    main()
