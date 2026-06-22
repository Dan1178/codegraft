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

# Measure how well ranking surfaces the right files, using your own git
# history as the answer key — no API call, no key needed:
codegraft eval --last 20 --ablation
```

The plan lands in `plans/<date>-<slug>.md`. No key yet? `codegraft plan --stub`
writes an offline placeholder so you can see the output shape.

## Example

`inspect` is the engine's window — ranked files with an explainable score
breakdown, plus an estimate of the context it *avoids* sending:

```
Repo: /path/to/codegraft
Discovery: git ls-files  Kept: 77  Skipped: 0  Mode: normal
Primary: Python   Frameworks: Pydantic
Ranked files for: add an openai provider
┏━━━━┳━━━━━━━┳────────────────────────────────────┳──────────────────────────┓
┃  # ┃ Score ┃ Path                               ┃ Signals                  ┃
┃  1 ┃  13.6 ┃ src/codegraft/providers/anthropic… ┃ filename=+6.0 symbol=+4… ┃
┃  4 ┃   8.8 ┃ src/codegraft/planning/service.py  ┃ content=+4.8 symbol=+4.0 ┃
┃  9 ┃   5.4 ┃ src/codegraft/config.py            ┃ content=+4.4 symbol=+4.0 ┃
Context bundle: 12 snippets, 43960 chars (budget 50000)
Est. tokens (rough): ~10,990 tokens sent vs ~33,923 to read the 12 selected files in full — ~22,933 saved (68%)
```

The baseline is the **selected files read in full**, not the whole repo — the
realistic thing an agent would otherwise open. Comparing against the entire
codebase would inflate the number; no agent reads unrelated files to implement
one feature.

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
| `codegraft impact <file>` | What depends on a file — blast-radius triage before you edit (no model call). |
| `codegraft symbol <name>` | Fetch one symbol definition instead of reading the whole file (no model call). |
| `codegraft affected-tests <files…>` | Select the tests that depend on changed files (selection only — never runs them). |
| `codegraft eval` | Score ranking accuracy (recall@k / MRR) against your real git history — no model call. |
| `codegraft eval-impact` | Baseline for `impact_of`: how often co-changed files are import-linked, vs git history. |
| `codegraft eval-symbol` | Baseline for `get_symbol`: the read-side token savings vs a whole-file read. |
| `codegraft eval-tests` | Baseline for `affected_tests`: test-selection recall vs git history. |

Useful flags: `--repo`, `--subdir`, `--request-file`, `--provider anthropic|openai`,
`--model`, `--stdout`, `--json`, `--dry-run`, `--stub` (plan), `--snippets` (inspect),
`--last N`, `--k`, `--ablation`, `--no-import-edge` (eval), `--transitive` (impact),
`--in` (symbol), `--since <ref>` (affected-tests).

### Read-side context tools — `impact`, `symbol`, `affected-tests`

`select_context` answers "what files matter for this request?" These three answer
the *next* questions in a read-side loop — all deterministic, free, no model
call, no key:

- **`codegraft impact <file> [--transitive]`** — the files that import `<file>`,
  so you gauge blast radius *before* a risky change. Complements grep rather than
  replacing it: grep finds and updates the actual call sites; `impact` tells you
  how far the change reaches and what to re-verify.
- **`codegraft symbol <name> [--in <file>]`** — one definition (signature + body +
  span) from a *large* file, instead of `Read`-ing the whole thing. For a small
  file, a plain `Read` is fine and gives more context.
- **`codegraft affected-tests <files…> [--since <ref>]`** — the tests that
  (transitively) depend on changed files, so you run the relevant handful first.
  *Selection only — codegraft does not run them.*

All three are **heuristic** (a lightweight reference scan, not an AST/LSP): they
miss dynamic imports, re-exports, and ambiguous basenames, so every result is
stamped `resolution`/`completeness: "heuristic"`. Use them as fast triage, never
as a correctness oracle — and never skip a full test run before merge.

Each ships with a validator that measures its value against your own git history,
the same way `eval` grades ranking:

```bash
codegraft eval-impact --last 20    # % of co-changed file pairs the graph links
codegraft eval-symbol              # mean % of a file you skip by fetching a symbol
codegraft eval-tests --last 30     # recall of co-changed tests from source changes
```

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

A few things to keep in mind:

- **Commit-message quality affects the score.** A sharp subject ("Add RBAC to
  admin routes") is a strong request and ranks well; a vague one ("fix stuff")
  is a thin query and scores low — the ranker didn't fail, the question did.
- **Large commits are capped by the bundle size.** Recall is `hits / changed
  files`, and the bundle holds at most `max_ranked_files` (12). A commit that
  changed 20 files therefore can't exceed recall@12 = 0.6 no matter how good the
  ranking — so sprawling commits (often new-feature scaffolding) drag the
  *absolute* aggregate down. The `Found/Gold` column makes this visible.
- **Read it comparatively.** It ranks the current tree and commit-changed-files
  is noisy ground truth (and the cap above applies equally to both runs), so the
  *delta* between two runs (before/after a ranking change, or `--ablation`) is
  the trustworthy number — not the absolute score. It's the regression guard for
  the ranker.

## Use as an MCP server (for coding agents)

codegraft's engine is also exposed over the **Model Context Protocol**, so a
coding agent (Claude Code, etc.) can call it directly — no per-prompt API spend
for the part that matters.

### Install for Claude Code (step by step)

New to MCP? The mental model: an **MCP server** is a small program that exposes
"tools" an agent can call. Claude Code doesn't know about codegraft's tools until
you introduce them — once. Three moves: **install → register → restart.**

You need Python 3.11+ and the [Claude Code](https://claude.com/claude-code) CLI.

```bash
# 1. Install codegraft with the MCP extra (this adds the `codegraft-mcp` command).
pip install "codegraft[mcp]"           # or, from a clone: pip install ".[mcp]"

# 2. Register the server with Claude Code — "add a server named codegraft,
#    started by running the command codegraft-mcp".
claude mcp add codegraft codegraft-mcp

# 3. Restart Claude Code (or start a fresh session), then verify:
claude mcp list                         # codegraft should be listed
```

That's it. In a chat the tools appear as `select_context`, `impact_of`,
`get_symbol`, `affected_tests`, and `generate_plan`.

For an MCP client other than Claude Code, point it at the same stdio command
(`codegraft-mcp`) — see the JSON config at the end of this section.

Good to know:

- **No API key for the read-side tools.** `select_context`, `impact_of`,
  `get_symbol`, and `affected_tests` are deterministic and free. Only
  `generate_plan` calls an LLM and needs a provider key — separate and opt-in.
- **A running server doesn't pick up code changes.** After you update codegraft,
  restart the server (or Claude Code) so new/changed tools show up.
- **`-e` (editable) ties the server to a checked-out branch** — handy when hacking
  on codegraft, but for plain use prefer `pip install "codegraft[mcp]"` (no `-e`)
  so the tool set doesn't shift when you switch git branches.

### The tools

Four deterministic, free read-side tools plus one opt-in planner:

- **`select_context(request, repo, subdir?)`** — the deterministic context
  bundle: ranked files + bounded snippets for a request. **No LLM call, no key,
  no per-request cost.** Hands the agent the right files instantly so it explores
  less. This is the differentiated piece, and the entry point to the loop below.
- **`impact_of(target, repo, transitive?)`** — the files that import `target`, for
  blast-radius triage before a risky change. Complements grep (grep finds the call
  sites; this gauges reach + what to re-verify). Free, no LLM. Heuristic.
- **`get_symbol(name, repo, path?)`** — one definition (signature + body + span)
  from a *large* file, instead of a whole-file read (a plain read is fine for a
  small file). Free, no LLM. Heuristic location/extent.
- **`affected_tests(changed_files, repo)`** — the tests that depend on changed
  files, so the agent runs the relevant handful first. **Selection only — it does
  not run anything**, and being heuristic it can miss tests.
- **`generate_plan(request, repo, …)`** — the full structured plan via a provider.
  **Opt-in** (costs tokens / needs a key); use it when you want a reviewable plan
  artifact, not for context.

They compose into one read-side loop, each tool's description cross-referencing
the next so the agent discovers the chain from any entry point:

```
select_context(request)            # what files matter
  → get_symbol(name, path)         # one symbol from a LARGE file (Read is fine for small ones)
  → impact_of(file)                # blast radius before a risky change (grep still finds call sites)
  → (edit)
  → affected_tests(changed_files)  # pick the tests to run first (then run them)
```

The server is a thin adapter over the same `analyze_repo` engine the CLI uses —
one core, three interfaces (CLI, MCP, LLM providers).

### Make the agent reach for it automatically

Registering the server gives the agent the *tools*; one instruction makes it
*use* them at the right moment. Drop this **decision tree** into the agent's
system prompt or a `CLAUDE.md` (project or global) so it reaches for the right
tool at each step of the read-side loop instead of falling back to blind
grepping and whole-file reads:

> ## codegraft — read-side tools
>
> - Planning/implementing a feature or change → `select_context` **first** (ranked
>   files + snippets), before grepping/reading.
> - About to make a *risky* change to a shared file/symbol → `impact_of` to gauge
>   blast radius (what to re-verify). Complements grep — grep still finds and
>   updates the call sites; `impact_of` tells you how far the change reaches.
> - Need one function/class/selector from a *large* file → `get_symbol`, not a
>   whole-file Read (for a small file, a plain Read is fine and gives more context).
> - Just edited files and want fast feedback → `affected_tests` to pick the
>   relevant tests (then run them; codegraft does not run them for you).
>
> All are deterministic, need no API key, and cost no request tokens. The graph
> tools are heuristic — triage, not a guarantee. Skip them only for trivial
> changes you can already locate.

Or install the packaged **Claude Code skill** instead of pasting that by hand —
it carries the same trigger and workflow, so the agent reaches for
`select_context` on its own:

```bash
# global (all repos):
cp -r skills/codegraft-context ~/.claude/skills/
# or per-project:  cp -r skills/codegraft-context <your-repo>/.claude/skills/
```

For MCP clients other than Claude Code, point them at the same stdio command:

```json
{
  "mcpServers": {
    "codegraft": { "command": "codegraft-mcp" }
  }
}
```

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

**`eval` gold-set scoping (if justified).** `eval` currently treats every file a
commit changed as gold, weighted equally. Two refinements would sharpen the
absolute scores (the comparative delta is already unaffected):

- `--max-gold N` — skip commits whose change set exceeds the bundle size, so the
  aggregate isn't dragged by commits the bundle physically can't cover; print how
  many were skipped.
- `--diff-filter` — scope the gold set by git status (e.g. modified-only) to
  measure pure *retrieval* of existing files, separating it from from-scratch
  files the commit created. Caveat: excluding all additions can drop a genuinely
  central new file (the new `mcp.py` *is* the answer for "Add MCP server"), so
  this changes what's measured rather than strictly improving it.

Deferred until a real run shows the absolute scores misleading enough to act on.

## License

MIT
