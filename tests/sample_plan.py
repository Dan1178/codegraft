"""A realistic, fully-populated ImplementationPlan used for snapshot testing.

Metadata is fixed (no live timestamp) so rendering is deterministic and the
checked-in example under ``examples/sample_plans/`` stays byte-stable. This is a
test helper, not a test module.
"""

from __future__ import annotations

from codegraft.models.plan import (
    AgentPrompt,
    Confidence,
    GenerationMetadata,
    ImplementationPlan,
    PlanPhase,
    PlannedFileChange,
    ReviewedFile,
    RiskItem,
    RiskSeverity,
    TestItem,
)


def sample_plan() -> ImplementationPlan:
    """A representative RBAC plan for a small FastAPI-style service."""

    return ImplementationPlan(
        title="Add role-based access control to admin routes",
        feature_summary=(
            "Restrict admin-only endpoints so that only users with the `admin` role "
            "can reach them; non-admin users receive a 403. Build on the existing "
            "auth and user model rather than introducing a new framework."
        ),
        assumptions=[
            "Users are already authenticated; this change adds authorization only.",
            "A single `admin` role is sufficient for the first iteration.",
        ],
        open_questions=[
            "Should roles be stored as a single field or a many-to-many table?",
            "Are there existing non-admin routes that should also become role-aware?",
        ],
        relevant_architecture=(
            "FastAPI service with routers under app/routes, business logic under "
            "app/services, and SQLAlchemy models under app/models. Auth is handled "
            "by app/services/auth.py, which already resolves the current user."
        ),
        files_reviewed=[
            ReviewedFile(
                path="app/routes/admin.py",
                why_it_matters="Defines the admin endpoints that must be gated.",
                confidence=Confidence.high,
            ),
            ReviewedFile(
                path="app/services/auth.py",
                why_it_matters="Resolves the current user; the natural place to enforce roles.",
                confidence=Confidence.high,
            ),
            ReviewedFile(
                path="app/models/user.py",
                why_it_matters="User model that needs a role attribute.",
                confidence=Confidence.medium,
            ),
        ],
        files_likely_to_modify=[
            PlannedFileChange(
                path="app/models/user.py",
                expected_change="Add a `role` field defaulting to `member`.",
                reason="Roles must be persisted on the user.",
            ),
            PlannedFileChange(
                path="app/services/auth.py",
                expected_change="Add a `require_role(role)` dependency.",
                reason="Centralizes authorization so routes stay thin.",
            ),
            PlannedFileChange(
                path="app/routes/admin.py",
                expected_change="Apply the `require_role('admin')` dependency to each route.",
                reason="Enforces the 403 for non-admin users.",
            ),
        ],
        data_model_changes=[
            "Add `role: str` to the User model (default `member`).",
        ],
        api_service_changes=[
            "New `require_role` FastAPI dependency in app/services/auth.py.",
            "Admin routes return 403 for users without the `admin` role.",
        ],
        ui_changes=[],
        implementation_phases=[
            PlanPhase(
                name="Phase A: role on the user model",
                goal="Persist a role on each user.",
                likely_files=["app/models/user.py"],
                tasks=[
                    "Add a `role` field to the User model with default `member`.",
                    "Backfill existing users to `member`.",
                ],
                acceptance_criteria=["User objects expose a `role` attribute."],
                validation=["pytest tests/test_models.py"],
            ),
            PlanPhase(
                name="Phase B: authorization dependency",
                goal="Provide a reusable role check and apply it to admin routes.",
                likely_files=["app/services/auth.py", "app/routes/admin.py"],
                tasks=[
                    "Implement `require_role(role)` returning a FastAPI dependency.",
                    "Apply `require_role('admin')` to each admin route.",
                ],
                acceptance_criteria=[
                    "Admin routes return 403 for non-admin users.",
                    "Admin users reach the routes unchanged.",
                ],
                validation=["pytest tests/test_admin_routes.py"],
            ),
        ],
        risks=[
            RiskItem(
                description="Locking out existing admins if backfill defaults everyone to member.",
                severity=RiskSeverity.high,
                mitigation="Explicitly set known admin accounts to `admin` in the same change.",
            ),
            RiskItem(
                description="Other routes may implicitly rely on admin-only access.",
                severity=RiskSeverity.medium,
                mitigation="Audit routers for assumptions before shipping.",
            ),
        ],
        test_plan=[
            TestItem(
                kind="unit",
                description="`require_role` allows matching roles and rejects others.",
                target="tests/test_auth.py",
            ),
            TestItem(
                kind="integration",
                description="Admin route returns 403 for a member and 200 for an admin.",
                target="tests/test_admin_routes.py",
            ),
            TestItem(
                kind="regression",
                description="Existing authenticated flows still pass.",
            ),
        ],
        claude_code_prompts=[
            AgentPrompt(
                phase_name="Phase A: role on the user model",
                prompt=(
                    "Add a `role` field to the User model in app/models/user.py, "
                    "defaulting to 'member'. Update any user-creation code to set it, "
                    "and add a test in tests/test_models.py asserting the default."
                ),
            ),
            AgentPrompt(
                phase_name="Phase B: authorization dependency",
                prompt=(
                    "In app/services/auth.py add `require_role(role: str)` that returns "
                    "a FastAPI dependency raising HTTP 403 when the current user's role "
                    "does not match. Apply require_role('admin') to every route in "
                    "app/routes/admin.py. Add tests in tests/test_admin_routes.py "
                    "covering the 403 and 200 cases."
                ),
            ),
        ],
        definition_of_done=[
            "Admin routes reject non-admin users with 403.",
            "User model persists a role; known admins are set to `admin`.",
            "Unit and integration tests pass.",
        ],
        metadata=GenerationMetadata(
            provider="anthropic",
            model="claude-sonnet-4-6",
            repo_root="/example/fastapi-demo",
            timestamp="2026-06-11T12:00:00",
            ranked_file_count=12,
            reviewed_file_count=3,
        ),
    )
