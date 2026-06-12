"""The ImplementationPlan schema.

This is codegraft's central output contract. The whole architecture hinges on
the LLM returning *this* structure (validated) rather than free-form Markdown:
deterministic rendering, snapshot tests, and provider-agnostic behaviour all
depend on it.

Design notes:
- Every field has a description. Those descriptions double as the schema we hand
  to structured-output APIs, so they are written to guide the model.
- Defaults are empty lists / "None expected" so that a partial response still
  validates and every Markdown section can always render.
- Enums are kept as plain str-enums so they serialize cleanly into JSON Schema.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    """How sure we are that a file is actually relevant."""

    high = "high"
    medium = "medium"
    low = "low"


class RiskSeverity(str, Enum):
    """Relative severity of a risk item."""

    high = "high"
    medium = "medium"
    low = "low"


class ReviewedFile(BaseModel):
    """A file that was part of the evidence bundle the model actually saw.

    This is the anti-hallucination anchor: the model may only list files here
    that were genuinely included in the context bundle.
    """

    path: str = Field(description="Repo-relative path of the reviewed file.")
    why_it_matters: str = Field(
        description="One sentence on why this file is relevant to the request."
    )
    confidence: Confidence = Field(
        default=Confidence.medium,
        description="Confidence that this file is relevant to the change.",
    )


class PlannedFileChange(BaseModel):
    """A file the plan expects to create or modify."""

    path: str = Field(description="Repo-relative path expected to change.")
    expected_change: str = Field(
        description="What concretely changes in this file (e.g. 'add /audit route')."
    )
    reason: str = Field(description="Why this change is needed for the feature.")


class PlanPhase(BaseModel):
    """One bounded, independently-shippable phase of the implementation."""

    name: str = Field(description="Short phase name, e.g. 'Phase A: data model'.")
    goal: str = Field(description="The single outcome this phase delivers.")
    likely_files: list[str] = Field(
        default_factory=list,
        description="Repo-relative files this phase will most likely touch.",
    )
    tasks: list[str] = Field(
        default_factory=list, description="Ordered, concrete tasks for this phase."
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Observable conditions that mean the phase is done.",
    )
    validation: list[str] = Field(
        default_factory=list,
        description="Commands or checks that verify the phase (tests, manual steps).",
    )


class RiskItem(BaseModel):
    """A risk the implementer should be aware of."""

    description: str = Field(description="The risk, stated plainly.")
    severity: RiskSeverity = Field(
        default=RiskSeverity.medium, description="Relative severity of the risk."
    )
    mitigation: str = Field(
        default="", description="How to reduce or avoid the risk, if known."
    )


class TestItem(BaseModel):
    """A recommended test."""

    kind: str = Field(
        description="Test category: unit | integration | e2e | manual | regression."
    )
    description: str = Field(description="What the test should verify.")
    target: str = Field(
        default="", description="File, module, or endpoint the test exercises."
    )


class AgentPrompt(BaseModel):
    """A ready-to-paste handoff prompt for a coding agent, per phase."""

    phase_name: str = Field(description="The phase this prompt drives.")
    prompt: str = Field(
        description="Self-contained instructions for a coding agent to execute the phase."
    )


class GenerationMetadata(BaseModel):
    """Provenance for the plan: how, when, and against what it was generated."""

    provider: str = Field(default="", description="Provider name, e.g. 'anthropic'.")
    model: str = Field(default="", description="Model id used to generate the plan.")
    repo_root: str = Field(default="", description="Absolute path of the analyzed repo.")
    timestamp: str = Field(default="", description="ISO-8601 generation timestamp.")
    ranked_file_count: int = Field(
        default=0, description="How many files were ranked as candidates."
    )
    reviewed_file_count: int = Field(
        default=0, description="How many files were included in the evidence bundle."
    )
    context_tokens: int = Field(
        default=0,
        description="Estimated tokens in the context bundle. Filled by codegraft.",
    )
    tokens_saved: int = Field(
        default=0,
        description=(
            "Estimated tokens NOT sent vs. dumping all candidate files. "
            "Filled by codegraft."
        ),
    )


class ImplementationPlan(BaseModel):
    """The full structured plan returned by a provider and rendered to Markdown."""

    title: str = Field(description="Concise feature/plan title.")
    feature_summary: str = Field(
        description="One-paragraph summary of the request and intended outcome."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made and explicit unknowns to confirm.",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Questions whose answers would change the plan.",
    )
    relevant_architecture: str = Field(
        default="",
        description="Summary of the current architecture relevant to this change.",
    )
    files_reviewed: list[ReviewedFile] = Field(
        default_factory=list,
        description="Files actually present in the evidence bundle. No invented paths.",
    )
    files_likely_to_modify: list[PlannedFileChange] = Field(
        default_factory=list, description="Files the plan expects to create or change."
    )
    data_model_changes: list[str] = Field(
        default_factory=list,
        description="Tables, schemas, models, migrations, serialization changes.",
    )
    api_service_changes: list[str] = Field(
        default_factory=list,
        description="Endpoints, background jobs, services, auth, integrations.",
    )
    ui_changes: list[str] = Field(
        default_factory=list,
        description="Components, routes, forms, states, copy. Empty if none expected.",
    )
    implementation_phases: list[PlanPhase] = Field(
        default_factory=list, description="Ordered, bounded implementation phases."
    )
    risks: list[RiskItem] = Field(
        default_factory=list, description="Technical, product, and rollback risks."
    )
    test_plan: list[TestItem] = Field(
        default_factory=list, description="Recommended tests across categories."
    )
    claude_code_prompts: list[AgentPrompt] = Field(
        default_factory=list,
        description="Per-phase handoff prompts for a coding agent.",
    )
    definition_of_done: list[str] = Field(
        default_factory=list, description="Checklist of completion criteria."
    )
    metadata: GenerationMetadata = Field(
        default_factory=GenerationMetadata,
        description="Generation provenance. Filled in by codegraft, not the model.",
    )
