# codegraft

> Turn a feature request plus a real local repository into a structured,
> evidence-backed implementation plan for coding agents.

codegraft is a **local-first implementation-planning CLI**. Coding agents work
far better when handed the *right context*, a *bounded plan*, and *explicit
verification criteria*. codegraft manufactures those planning artifacts
automatically: it scans your repo, ranks the files that matter for a request,
extracts just enough evidence, asks a model for a **typed** plan, and renders it
to stable Markdown — including per-phase handoff prompts.

## Why it's not a thin wrapper

The value is the **deterministic pipeline around the model**:

```
repo + request → discovery → ignore/safety → ranking → snippet budgeting
              → ONE schema-constrained planning call → typed ImplementationPlan
              → deterministic Markdown + agent prompts → plans/<date>-<slug>.md
```

Everything except the single planning call is deterministic and unit-tested.

## Quickstart

```bash
pip install -e ".[dev]"

codegraft init                              # write codegraft.toml
# set ANTHROPIC_API_KEY (and/or OPENAI_API_KEY) in your environment or .env

codegraft plan "Add RBAC to admin routes" --repo .
```

The plan lands in `plans/<date>-<slug>.md`.

> **Status:** Phase 1 (foundation & contract). The `plan` command currently
> writes a clearly-marked **stub** plan to prove the end-to-end path. Real repo
> analysis and provider calls arrive in later phases — see [CLAUDE.md](CLAUDE.md).

## Commands

| Command | Purpose |
|---------|---------|
| `codegraft init` | Write a default `codegraft.toml`; report required env keys. |
| `codegraft inspect "<request>"` | Preview ranked files/evidence (no model call). *(Phase 3)* |
| `codegraft plan "<request>"` | Generate a plan and write it to `plans/`. |

## Limitations (by design, for V1)

Large monorepos degrade gracefully (use `--subdir`). No embeddings, no
tree-sitter, no remote repos, no diff validation, no web UI. See the scope
guardrails in [CLAUDE.md](CLAUDE.md).

## License

MIT
