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
from codegraft.repo.discover import discover_repo
from codegraft.repo.graph import affected_tests, impact_of
from codegraft.repo.summarize import summarize
from codegraft.repo.symbols import find_symbol


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


def impact_of_payload(
    target: str, repo: str = ".", transitive: bool = False
) -> dict[str, Any]:
    """Reverse-dependency lookup for *target* — the files that import it.

    Minimal JSON: the resolved path, its importers, and a ``resolution`` trust
    flag. ``resolved`` is ``null`` and ``ambiguous`` is populated when the target
    matched zero or several files, so the caller can disambiguate.
    """

    root = Path(repo)
    config = Config.load(root)
    scan = discover_repo(root, config)
    result = impact_of(target, scan, root, config, transitive=transitive)

    payload: dict[str, Any] = {
        "target": result.target,
        "resolved": result.resolved,
        "imported_by": result.imported_by,
        "resolution": result.resolution,
    }
    if transitive:
        payload["transitive"] = result.transitive
    if result.ambiguous:
        payload["ambiguous"] = result.ambiguous
    return payload


def affected_tests_payload(
    changed_files: list[str], repo: str = "."
) -> dict[str, Any]:
    """Tests that depend on *changed_files* (selection only — nothing is run)."""

    root = Path(repo)
    config = Config.load(root)
    scan = discover_repo(root, config)
    summary = summarize(scan)
    result = affected_tests(changed_files, scan, summary, root, config)

    payload: dict[str, Any] = {
        "changed": result.changed,
        "tests": result.tests,
        "completeness": result.completeness,
    }
    if result.unresolved:
        payload["unresolved"] = result.unresolved
    return payload


def get_symbol_payload(
    name: str, repo: str = ".", path: str | None = None
) -> dict[str, Any]:
    """One bounded definition of *name* instead of a whole-file read.

    Returns every match (a name can be defined in several places) as minimal
    JSON: path, signature, 1-based span, the line-numbered snippet, and a
    ``resolution`` trust flag.
    """

    root = Path(repo)
    config = Config.load(root)
    scan = discover_repo(root, config)
    hits = find_symbol(name, scan, root, config, in_path=path)
    return {
        "name": name,
        "resolution": "heuristic",
        "matches": [
            {
                "path": h.path,
                "signature": h.signature,
                "span": [h.span[0], h.span[1]],
                "snippet": h.snippet,
                "truncated": h.truncated,
            }
            for h in hits
        ],
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
        """Call this FIRST when asked to plan or implement a feature, fix, or change
        in a repository — before manually grepping or reading files. Returns the most
        relevant files (ranked, with a score breakdown) plus bounded code snippets for
        the request, so you start from the right context instead of exploring blind.
        Deterministic: no LLM call, no API key, no per-request cost. `repo` is a local
        path (prefer an absolute path); `subdir` scopes a large repo. Skip only for
        trivial single-file changes you can already locate."""

        return select_context_payload(request, repo, subdir)

    @server.tool()
    def impact_of(
        target: str, repo: str = ".", transitive: bool = False
    ) -> dict[str, Any]:
        """Call this BEFORE editing a shared file, instead of grepping for who imports
        it. Returns the files that depend on `target` so you can judge blast radius up
        front — a natural follow-up to `select_context` on a file you intend to change.
        Deterministic, free, no LLM. Resolution is heuristic (misses dynamic imports /
        re-exports / ambiguous basenames), so use it as blast-radius triage, not a
        guarantee. `target` is a repo-relative path or a bare filename; set
        `transitive=True` for the full reverse closure. Single-shot and bounded — not a
        background indexer; skip it for a file you already know is a leaf."""

        return impact_of_payload(target, repo, transitive)

    @server.tool()
    def get_symbol(
        name: str, repo: str = ".", path: str | None = None
    ) -> dict[str, Any]:
        """Call this instead of reading a whole file when you need one
        function/class/CSS selector — a natural follow-up to `select_context` once it
        points you at a file. Returns just that definition: signature, body, and a
        line-numbered snippet. Free, no LLM, tiny payload. Heuristic location and
        extent (not compiler-accurate) — for exact cross-file resolution use your
        editor's go-to-definition. `name` is style-insensitive (adminPanel matches
        admin_panel); pass `path` to scope to one file, else all matches are returned."""

        return get_symbol_payload(name, repo, path)

    @server.tool()
    def affected_tests(changed_files: list[str], repo: str = ".") -> dict[str, Any]:
        """After editing, call this to get the tests that depend on your changed files,
        so you run the relevant handful first instead of the whole suite. Pass the file
        list `select_context` or `impact_of` surfaced. Selection only — it does NOT run
        anything, and being heuristic it can miss tests, so run the full suite before
        merging. Deterministic, free, no LLM."""

        return affected_tests_payload(changed_files, repo)

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
