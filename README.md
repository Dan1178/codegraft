# codegraft

> Turn a feature request plus a real local repository into a structured,
> evidence-backed implementation plan for coding agents.

codegraft is a **local-first implementation-planning CLI**. Coding agents (Claude
Code and friends) work far better when handed the *right context*, a *bounded
plan*, and *explicit verification criteria*. codegraft manufactures those
artifacts automatically: it scans your repo, ranks the files that matter for a
request, extracts just enough evidence, asks a model for a **typed** plan, and
renders it to stable Markdown — including per-phase handoff prompts.

## Why this exists

Brownfield change is the hard case. Repo-packers (Repomix, Gitingest) turn a repo
into a prompt digest; full agents (Aider, Cody, Plandex) try to do everything.
The gap in between is *planning*: taking "add RBAC to the admin routes" plus a
real codebase and producing a bounded, reviewable engineering plan with impacted
files, risks, tests, and agent prompts. That's the seat codegraft fills.

## What makes it more than a wrapper

The value is the **deterministic pipeline around the model** — everything except
one schema-constrained call is deterministic and unit-tested:

```
repo + request
  → discovery (git-aware) → ignore / safety filtering
  → repo summary + ranking (explainable score per file)
  → bounded snippet extraction (under a token budget)
  → ONE schema-constrained planning call → typed ImplementationPlan
  → deterministic Markdown + per-phase agent prompts
  → plans/<date>-<slug>.md
```

A privacy consequence falls out of this design: **your repo stays local** — only
the small, selected snippet bundle is ever sent to a provider.

## Quickstart

```bash
pip install -e ".[dev,anthropic]"      # add ,openai for the OpenAI provider

codegraft init                         # write codegraft.toml
# set ANTHROPIC_API_KEY in your environment or a .env file

# Preview what codegraft sees & ranks — no API call, no key needed:
codegraft inspect "Add RBAC to admin routes" --repo .

# Generate a real plan via Anthropic:
codegraft plan "Add RBAC to admin routes" --repo .
```

The plan lands in `plans/<date>-<slug>.md`. No key yet? `codegraft plan --stub`
writes an offline placeholder so you can see the output shape.

## Example

`inspect` is the engine's window — ranked files with an explainable score
breakdown, plus an estimate of the context it *avoids* sending:

```
Repo: /path/to/codegraft
Discovery: git ls-files  Kept: 57  Skipped: 0  Mode: normal
Primary: Python   Frameworks: Pydantic
Ranked files for: add an openai provider
┏━━━━┳━━━━━━━┳────────────────────────────────────┳──────────────────────────┓
┃  # ┃ Score ┃ Path                               ┃ Signals                  ┃
┃  1 ┃  13.6 ┃ src/codegraft/providers/anthropic… ┃ filename=+6.0 symbol=+4… ┃
┃  4 ┃   8.8 ┃ src/codegraft/planning/service.py  ┃ content=+4.8 symbol=+4.0 ┃
┃  9 ┃   5.4 ┃ src/codegraft/config.py            ┃ content=+4.4 symbol=+4.0 ┃
Context bundle: 12 snippets, 38304 chars (budget 50000)
Est. tokens (rough): ~9,576 sent vs ~56,200 for all 57 candidate files — ~46,624 saved (83%)
```

- A long-form request: [examples/demo_requests/add-rbac.md](examples/demo_requests/add-rbac.md)
- A rendered plan: [examples/sample_plans/add-rbac.md](examples/sample_plans/add-rbac.md)

> Long requests don't dilute ranking: a verbose request file is ranked by its
> heading/first sentence (the *signal*), while the full text still goes to the
> model. Preview it with `codegraft inspect --request-file <file> --repo .`.

## Commands

| Command | Purpose |
|---------|---------|
| `codegraft init` | Write a default `codegraft.toml`; report required env keys. |
| `codegraft inspect "<request>"` | Preview ranked files, score breakdown, snippets, token estimate (no model call). |
| `codegraft plan "<request>"` | Generate a plan and write it to `plans/`. |
| `codegraft eval` | Score ranking accuracy (recall@k / MRR) against your real git history — no model call. |

Useful flags: `--repo`, `--subdir`, `--request-file`, `--provider anthropic|openai`,
`--model`, `--stdout`, `--json`, `--dry-run`, `--stub` (plan), `--snippets` (inspect),
`--last N`, `--k`, `--ablation`, `--no-import-edge` (eval).

### Measuring ranking quality — `codegraft eval`

How good is `inspect` at surfacing the *right* files? `eval` answers that
deterministically, with no API call, by turning your git history into a
benchmark. From each commit it pulls **two** things, playing two different roles:

- the **commit subject → the request** (the *question*): fed to the same ranker
  `inspect` uses, exactly as if you'd typed it. The message doesn't define the
  ranking — it's just the query the ranker responds to.
- the **files that commit changed → the gold set** (the *answer key*): used to
  grade whether the ranker actually surfaced them.

```
commit subject ───────► request ──► [ranker] ──► ranked files ─┐
commit's changed files ─► gold set ────────────────────────────┤
                                              compare → recall@k, MRR
```

It then reports **recall@k** (did the changed files land in the top-k bundle?)
and **MRR** (how high did the first one rank?).

```bash
codegraft eval --last 20 --k 12        # score the most recent 20 commits
codegraft eval --ablation              # run with vs without a ranking signal, show the delta
codegraft eval <sha> <sha> --json      # specific commits, machine-readable
```

Two things to keep in mind:

- **Commit-message quality affects the score.** A sharp subject ("Add RBAC to
  admin routes") is a strong request and ranks well; a vague one ("fix stuff")
  is a thin query and scores low — the ranker didn't fail, the question did.
- **Read it comparatively.** It ranks the current tree and commit-changed-files
  is noisy ground truth, so the *delta* between two runs (before/after a ranking
  change, or `--ablation`) is the trustworthy number — not the absolute score.
  It's the regression guard for the ranker.

## Use as an MCP server (for coding agents)

codegraft's engine is also exposed over the **Model Context Protocol**, so a
coding agent (Claude Code, etc.) can call it directly — no per-prompt API spend
for the part that matters:

```bash
pip install -e ".[mcp]"
# register the stdio server with Claude Code:
claude mcp add codegraft codegraft-mcp
```

Two tools:

- **`select_context(request, repo, subdir?)`** — the deterministic context
  bundle: ranked files + bounded snippets for a request. **No LLM call, no key,
  no per-request cost.** Hands the agent the right files instantly so it explores
  less. This is the differentiated piece.
- **`generate_plan(request, repo, …)`** — the full structured plan via a provider.
  **Opt-in** (costs tokens / needs a key); use it when you want a reviewable plan
  artifact, not for context.

The server is a thin adapter over the same `analyze_repo` engine the CLI uses —
one core, three interfaces (CLI, MCP, LLM providers).

## Architecture notes

- **Typed output contract.** Providers return a validated `ImplementationPlan`
  (Pydantic), never free-form Markdown. Rendering, tests, and `--json` all build
  on the schema. See [docs/architecture.md](docs/architecture.md).
- **Provider abstraction.** Anthropic and OpenAI sit behind one `PlanProvider`
  protocol and share the *identical* prompt assembly; only the SDK call differs.
- **Deterministic analysis layer.** Discovery, ignore/safety, ranking, and
  snippet budgeting are pure and testable — `inspect` exposes all of it.
- **Provenance you can trust.** Generation metadata (provider, model, token
  estimate, file counts) is stamped by codegraft, not authored by the model.

## Limitations (by design, for V1)

Large monorepos degrade gracefully (use `--subdir`). No embeddings, no
tree-sitter, no remote repos, no diff validation, no web UI. Ranking is a
deterministic heuristic, not semantic search. Token counts are estimates
(~4 chars/token), not exact. See the scope guardrails in [CLAUDE.md](CLAUDE.md).

## Roadmap

Focused V2 candidates only: an anti-hallucination validator (assert every
reviewed file exists in the bundle), optional prompt caching for repeated runs,
a narrow Python-only AST summarizer, and an opt-in plan-vs-diff reviewer.

## License

MIT
