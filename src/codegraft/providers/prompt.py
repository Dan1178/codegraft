"""Deterministic prompt assembly shared by all providers.

The system prompt (role, rules, output rubric) is a static package resource; the
user message is assembled from the evidence bundle with XML-tagged sections —
the structure Anthropic recommends when a prompt mixes instructions, context,
and variable inputs. Keeping this provider-agnostic means Anthropic and OpenAI
send the model the exact same context.
"""

from __future__ import annotations

from importlib import resources

from codegraft.providers.base import PlanningRequest

_SYSTEM_PROMPT: str | None = None


def system_prompt() -> str:
    """Load (and cache) the planner system prompt from package resources."""

    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = (
            resources.files("codegraft.prompts")
            .joinpath("planner_system.md")
            .read_text(encoding="utf-8")
        )
    return _SYSTEM_PROMPT


def _summary_block(req: PlanningRequest) -> str:
    s = req.summary
    return "\n".join(
        [
            f"Primary language: {s.primary_language or 'unknown'}",
            f"Frameworks: {', '.join(s.frameworks) or 'none detected'}",
            f"Manifests: {', '.join(s.manifests) or 'none'}",
            f"Entry points: {', '.join(s.entry_points) or 'none detected'}",
            f"Test paths: {', '.join(s.test_paths) or 'none detected'}",
            f"Candidate files: {s.file_count} (scale mode: {s.mode})",
        ]
    )


def _ranked_block(req: PlanningRequest) -> str:
    if not req.ranked:
        return "(no files ranked)"
    return "\n".join(f"- {r.path} (score {r.score:.1f})" for r in req.ranked)


def _snippets_block(req: PlanningRequest) -> str:
    if not req.snippets:
        return "(no snippets extracted)"
    blocks = [
        f'<file path="{s.path}">\n{s.content}\n</file>' for s in req.snippets
    ]
    return "\n".join(blocks)


def build_user_message(req: PlanningRequest) -> str:
    """Assemble the XML-tagged user message from the evidence bundle."""

    return "\n\n".join(
        [
            f"<feature_request>\n{req.feature_request}\n</feature_request>",
            f"<repo_summary>\n{_summary_block(req)}\n</repo_summary>",
            f"<directory_tree>\n{req.summary.directory_tree}\n</directory_tree>",
            f"<ranked_files>\n{_ranked_block(req)}\n</ranked_files>",
            f"<file_snippets>\n{_snippets_block(req)}\n</file_snippets>",
        ]
    )


def build_planning_prompt(req: PlanningRequest) -> tuple[str, str]:
    """Return ``(system_prompt, user_message)`` for *req*."""

    return system_prompt(), build_user_message(req)
