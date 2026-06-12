# Add role-based access control to admin routes

## Feature Summary

Restrict admin-only endpoints so that only users with the `admin` role can reach them; non-admin users receive a 403. Build on the existing auth and user model rather than introducing a new framework.

## Assumptions

- Users are already authenticated; this change adds authorization only.
- A single `admin` role is sufficient for the first iteration.

## Open Questions

- Should roles be stored as a single field or a many-to-many table?
- Are there existing non-admin routes that should also become role-aware?

## Relevant Architecture

FastAPI service with routers under app/routes, business logic under app/services, and SQLAlchemy models under app/models. Auth is handled by app/services/auth.py, which already resolves the current user.

## Files Reviewed

| Path | Why It Matters | Confidence |
|------|----------------|------------|
| `app/routes/admin.py` | Defines the admin endpoints that must be gated. | high |
| `app/services/auth.py` | Resolves the current user; the natural place to enforce roles. | high |
| `app/models/user.py` | User model that needs a role attribute. | medium |

## Files Likely To Modify

| Path | Expected Change | Reason |
|------|-----------------|--------|
| `app/models/user.py` | Add a `role` field defaulting to `member`. | Roles must be persisted on the user. |
| `app/services/auth.py` | Add a `require_role(role)` dependency. | Centralizes authorization so routes stay thin. |
| `app/routes/admin.py` | Apply the `require_role('admin')` dependency to each route. | Enforces the 403 for non-admin users. |

## Data Model Changes

- Add `role: str` to the User model (default `member`).

## API And Service Changes

- New `require_role` FastAPI dependency in app/services/auth.py.
- Admin routes return 403 for users without the `admin` role.

## UI Changes

_None expected._

## Implementation Phases

### Phase A: role on the user model

**Goal**
Persist a role on each user.

**Likely files**
- app/models/user.py

**Tasks**
- Add a `role` field to the User model with default `member`.
- Backfill existing users to `member`.

**Acceptance criteria**
- User objects expose a `role` attribute.

**Validation**
- pytest tests/test_models.py

### Phase B: authorization dependency

**Goal**
Provide a reusable role check and apply it to admin routes.

**Likely files**
- app/services/auth.py
- app/routes/admin.py

**Tasks**
- Implement `require_role(role)` returning a FastAPI dependency.
- Apply `require_role('admin')` to each admin route.

**Acceptance criteria**
- Admin routes return 403 for non-admin users.
- Admin users reach the routes unchanged.

**Validation**
- pytest tests/test_admin_routes.py

## Risks

- **[high]** Locking out existing admins if backfill defaults everyone to member. _Mitigation: Explicitly set known admin accounts to `admin` in the same change._
- **[medium]** Other routes may implicitly rely on admin-only access. _Mitigation: Audit routers for assumptions before shipping._

## Test Plan

- **unit**: `require_role` allows matching roles and rejects others. (`tests/test_auth.py`)
- **integration**: Admin route returns 403 for a member and 200 for an admin. (`tests/test_admin_routes.py`)
- **regression**: Existing authenticated flows still pass.

## Claude Code Prompts

### Prompt For Phase A: role on the user model

```text
Add a `role` field to the User model in app/models/user.py, defaulting to 'member'. Update any user-creation code to set it, and add a test in tests/test_models.py asserting the default.
```

### Prompt For Phase B: authorization dependency

```text
In app/services/auth.py add `require_role(role: str)` that returns a FastAPI dependency raising HTTP 403 when the current user's role does not match. Apply require_role('admin') to every route in app/routes/admin.py. Add tests in tests/test_admin_routes.py covering the 403 and 200 cases.
```

## Definition Of Done

- Admin routes reject non-admin users with 403.
- User model persists a role; known admins are set to `admin`.
- Unit and integration tests pass.

## Generation Metadata

- Provider: anthropic
- Model: claude-sonnet-4-6
- Repo root: /example/fastapi-demo
- Timestamp: 2026-06-11T12:00:00
- Ranked file count: 12
- Reviewed file count: 3
