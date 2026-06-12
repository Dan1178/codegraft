"""Render an :class:`ImplementationPlan` into stable Markdown.

Rules that make this safe to snapshot-test and pleasant to read:

- Every major section is *always* rendered. Empty lists become an explicit
  "None expected." line rather than a missing heading.
- Claude Code prompts are rendered from structured phase data, never a second
  free-form model pass.
- Output is pure: same plan in, byte-identical Markdown out (modulo the
  timestamp the caller puts in metadata).
"""

from __future__ import annotations

from codegraft.models.plan import ImplementationPlan

_NONE = "_None expected._"


def _cell(text: str) -> str:
    """Make a string safe inside a Markdown table cell.

    A literal ``|`` or a newline in a model-produced path/reason would otherwise
    break the table layout. Escape pipes and flatten newlines.
    """

    return text.replace("|", "\\|").replace("\n", " ").strip()


def _bullets(items: list[str]) -> str:
    if not items:
        return _NONE
    return "\n".join(f"- {item}" for item in items)


def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body}\n"


def render_markdown(plan: ImplementationPlan) -> str:
    """Render a plan to a complete Markdown document."""

    parts: list[str] = [f"# {plan.title}\n"]

    parts.append(_section("Feature Summary", plan.feature_summary or _NONE))
    parts.append(_section("Assumptions", _bullets(plan.assumptions)))
    parts.append(_section("Open Questions", _bullets(plan.open_questions)))
    parts.append(
        _section("Relevant Architecture", plan.relevant_architecture or _NONE)
    )

    # Files Reviewed — the anti-hallucination anchor.
    if plan.files_reviewed:
        rows = ["| Path | Why It Matters | Confidence |", "|------|----------------|------------|"]
        for f in plan.files_reviewed:
            rows.append(f"| `{_cell(f.path)}` | {_cell(f.why_it_matters)} | {f.confidence.value} |")
        files_reviewed = "\n".join(rows)
    else:
        files_reviewed = _NONE
    parts.append(_section("Files Reviewed", files_reviewed))

    # Files Likely To Modify — the actionable handoff.
    if plan.files_likely_to_modify:
        rows = ["| Path | Expected Change | Reason |", "|------|-----------------|--------|"]
        for f in plan.files_likely_to_modify:
            rows.append(f"| `{_cell(f.path)}` | {_cell(f.expected_change)} | {_cell(f.reason)} |")
        files_modify = "\n".join(rows)
    else:
        files_modify = _NONE
    parts.append(_section("Files Likely To Modify", files_modify))

    parts.append(_section("Data Model Changes", _bullets(plan.data_model_changes)))
    parts.append(_section("API And Service Changes", _bullets(plan.api_service_changes)))
    parts.append(_section("UI Changes", _bullets(plan.ui_changes)))

    # Implementation Phases.
    if plan.implementation_phases:
        phase_blocks: list[str] = []
        for phase in plan.implementation_phases:
            block = [
                f"### {phase.name}",
                "",
                f"**Goal**\n{phase.goal or _NONE}",
                "",
                "**Likely files**",
                _bullets(phase.likely_files),
                "",
                "**Tasks**",
                _bullets(phase.tasks),
                "",
                "**Acceptance criteria**",
                _bullets(phase.acceptance_criteria),
                "",
                "**Validation**",
                _bullets(phase.validation),
            ]
            phase_blocks.append("\n".join(block))
        phases_body = "\n\n".join(phase_blocks)
    else:
        phases_body = _NONE
    parts.append(_section("Implementation Phases", phases_body))

    # Risks.
    if plan.risks:
        risk_lines = [
            f"- **[{r.severity.value}]** {r.description}"
            + (f" _Mitigation: {r.mitigation}_" if r.mitigation else "")
            for r in plan.risks
        ]
        risks_body = "\n".join(risk_lines)
    else:
        risks_body = _NONE
    parts.append(_section("Risks", risks_body))

    # Test Plan.
    if plan.test_plan:
        test_lines = [
            f"- **{t.kind}**: {t.description}"
            + (f" (`{t.target}`)" if t.target else "")
            for t in plan.test_plan
        ]
        tests_body = "\n".join(test_lines)
    else:
        tests_body = _NONE
    parts.append(_section("Test Plan", tests_body))

    # Claude Code Prompts — rendered from structured phase data.
    if plan.claude_code_prompts:
        prompt_blocks = [
            f"### Prompt For {p.phase_name}\n\n```text\n{p.prompt}\n```"
            for p in plan.claude_code_prompts
        ]
        prompts_body = "\n\n".join(prompt_blocks)
    else:
        prompts_body = _NONE
    parts.append(_section("Claude Code Prompts", prompts_body))

    parts.append(_section("Definition Of Done", _bullets(plan.definition_of_done)))

    # Generation Metadata.
    m = plan.metadata
    meta_lines = [
        f"- Provider: {m.provider or '—'}",
        f"- Model: {m.model or '—'}",
        f"- Repo root: {m.repo_root or '—'}",
        f"- Timestamp: {m.timestamp or '—'}",
        f"- Ranked file count: {m.ranked_file_count}",
        f"- Reviewed file count: {m.reviewed_file_count}",
    ]
    parts.append(_section("Generation Metadata", "\n".join(meta_lines)))

    return "\n".join(parts).rstrip() + "\n"
