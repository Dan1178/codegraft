"""Renderer tests: every required section must always appear."""

from __future__ import annotations

from pathlib import Path

from codegraft.models.plan import ImplementationPlan, PlannedFileChange
from codegraft.planning.renderer import render_markdown
from tests.sample_plan import sample_plan

SAMPLE_PLAN_FILE = (
    Path(__file__).resolve().parents[1] / "examples" / "sample_plans" / "add-rbac.md"
)

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


def test_sample_plan_matches_snapshot() -> None:
    """Rendering the sample plan must match the checked-in example byte-for-byte.

    If this fails after an intentional renderer change, regenerate the example:
        python -c "import sys; sys.path.insert(0,'tests'); from sample_plan import
        sample_plan; from codegraft.planning.renderer import render_markdown;
        open('examples/sample_plans/add-rbac.md','w',encoding='utf-8').write(
        render_markdown(sample_plan()))"
    """

    rendered = render_markdown(sample_plan())
    expected = SAMPLE_PLAN_FILE.read_text(encoding="utf-8")
    assert rendered == expected


def test_table_cells_escape_pipes() -> None:
    """A literal pipe in a path/reason must not break the Markdown table."""

    plan = ImplementationPlan(
        title="t",
        feature_summary="s",
        files_likely_to_modify=[
            PlannedFileChange(
                path="a|b.py", expected_change="do x | y", reason="because | reasons"
            )
        ],
    )
    md = render_markdown(plan)
    # The only unescaped pipes in the row are the 4 column delimiters.
    row = next(ln for ln in md.splitlines() if "a\\|b.py" in ln)
    assert row.count("|") - row.count("\\|") == 4
