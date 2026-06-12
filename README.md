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
pip install -e ".[dev,anthropic]"

codegraft init                              # write codegraft.toml
# set ANTHROPIC_API_KEY in your environment or a .env file

codegraft inspect "Add RBAC to admin routes" --repo .   # preview (no API call)
codegraft plan "Add RBAC to admin routes" --repo .      # real plan via Anthropic
```

The plan lands in `plans/<date>-<slug>.md`.

> **Status:** Phases 1–4 complete. `inspect` and `plan` both work end to end —
> `plan` runs the deterministic analysis, calls Anthropic for a schema-validated
> `ImplementationPlan`, and renders Markdown. `codegraft plan --stub` produces an
> offline placeholder with no API key. The OpenAI provider and final portfolio
> polish are the remaining phases — see [CLAUDE.md](CLAUDE.md).

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
