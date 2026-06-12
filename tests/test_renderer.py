"""Renderer tests: every required section must always appear."""

from __future__ import annotations

from codegraft.models.plan import ImplementationPlan
from codegraft.planning.renderer import render_markdown

REQUIRED_SECTIONS = [
    "## Feature Summary",
    "## Assumptions",
    "## Open Questions",
    "## Relevant Architecture",
    "## Files Reviewed",
    "## Files Likely To Modify",
    "## Data Model Changes",
    "## API And Service Changes",
    "## UI Changes",
    "## Implementation Phases",
    "## Risks",
    "## Test Plan",
    "## Claude Code Prompts",
    "## Definition Of Done",
    "## Generation Metadata",
]


def test_minimal_plan_renders_all_sections() -> None:
    """A plan with only the required fields still renders every section."""

    plan = ImplementationPlan(title="Tiny", feature_summary="Just a summary.")
    md = render_markdown(plan)

    assert md.startswith("# Tiny\n")
    for section in REQUIRED_SECTIONS:
        assert section in md, f"missing section: {section}"
    # Empty lists collapse to an explicit placeholder, never a blank section.
    assert "_None expected._" in md


def test_render_is_deterministic() -> None:
    plan = ImplementationPlan(title="X", feature_summary="Y")
    assert render_markdown(plan) == render_markdown(plan)
