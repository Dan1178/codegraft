# Add role-based access control to admin routes

We need to restrict the admin-only endpoints so that only users with an
appropriate role can reach them. Right now any authenticated user can call the
admin routes.

## Goals
- Introduce a notion of roles (at minimum `admin` and `member`).
- Gate the admin routes so a non-admin user receives a 403.
- Keep the change small and consistent with the existing service structure.

## Constraints
- Do not add a new auth framework; build on the existing auth/service code.
- Follow the project's existing conventions for routes, services, and models.
- Include tests that cover both the allowed and forbidden paths.
- No database migration if it can be avoided; prefer a role field on the user.

## Out of scope
- A full permissions/policy system.
- A UI for managing roles.
