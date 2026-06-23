# CLAUDE.md — codegraft

Guidance for AI coding agents working in this repository.

## What this is

codegraft is a **local-first implementation-planning CLI**. It takes a feature
request plus a real local repository and produces a structured, evidence-backed
Markdown implementation plan (impacted files, risks, tests, phased steps, and
per-phase handoff prompts) for coding agents.

The core bet: a **deterministic pipeline** does all the repo work (discovery,
ignore/safety, ranking, snippet extraction), then **one schema-constrained LLM
call** returns a typed `ImplementationPlan`, then **deterministic rendering**
turns it into Markdown. Everything except the single planning call is testable
without a model.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run the CLI
codegraft --help
codegraft init
codegraft plan "Add RBAC to admin routes" --repo .

# Measure ranking quality against real git history (no model call). Read the
# *delta* (e.g. --ablation), not the absolute score. Use it to validate any
# change to repo/rank.py before trusting a single-case A/B.
codegraft eval --last 20 --ablation --k 12

# Read-side context tools (deterministic, no model call) — see Phase 7.
codegraft impact src/codegraft/repo/rank.py        # who imports this?
codegraft symbol rank_files --in src/codegraft/repo/rank.py
codegraft affected-tests src/codegraft/repo/graph.py --since HEAD~1

# Each read-side tool has a validator that baselines its value vs git history,
# exactly like `eval` does for ranking. Run after changing repo/imports.py,
# repo/graph.py, or repo/symbols.py.
codegraft eval-impact --last 20     # impact_of: co-change pair linkage
codegraft eval-symbol               # get_symbol: read-side token savings
codegraft eval-tests --last 30      # affected_tests: test-selection recall

# Tests
pytest                  # all deterministic + mocked tests
pytest -m live_anthropic  # opt-in, hits the real API (needs ANTHROPIC_API_KEY)
```

## Architecture (boundaries to respect)

```
repo path + request
  → CLI + config        (cli.py, config.py)
  → repo analysis       (repo/*: discover, ignore, safety, tree, detect,
                         summarize, rank, snippets)   [deterministic]
  → PlanningRequest
  → provider adapter    (providers/*: base + anthropic + openai)  [the ONE call]
  → ImplementationPlan  (models/plan.py)               [validated]
  → renderer            (planning/renderer.py)          [deterministic]
  → plans/<date>-<slug>.md
```

Read-side query tools share the analysis layer but bypass the provider entirely
(deterministic, no model call):

```
repo/imports.py  → build_import_graph (forward+reverse edges; resolver shared
                   with rank.py's imported_by signal — keep it byte-for-byte)
repo/graph.py    → impact_of (reverse deps), affected_tests (reverse closure ∩ tests)
repo/symbols.py  → find_symbol (snippet extractor at symbol granularity)
```

- `models/plan.py` is the **output contract**. Provider adapters must return a
  validated `ImplementationPlan`, never Markdown.
- Keep provider-specific code inside its adapter.
- The renderer must always emit every section (empty → "None expected.").
- Claude Code prompts are rendered from structured phase data, not a 2nd LLM call.

## Build phases (current status)

1. ✅ **Foundation & contract** — package, typed config + plan models, Typer CLI,
   stub plan path writing Markdown, 14 passing tests. **Done.**
2. ✅ **Discovery & ignore engine** — git ls-files (tracked/untracked), PathSpec
   nested-gitignore fallback, safety denylist (secrets/binaries/oversized),
   typed `RepoScan`, real `inspect` discovery preview, 27 passing tests. **Done.**
3. ✅ **Repo summary, ranking, snippet extraction** — compact tree, language/
   framework detection, two-stage explainable ranking, bounded snippets,
   `analyze_repo` entry point, scored `inspect` with `--subdir`/`--snippets`,
   43 passing tests. **Done.**
4. ✅ **Anthropic provider** — `PlanProvider` protocol + `PlanningRequest`,
   XML prompt assembly (system prompt as package resource), structured output
   via `messages.parse(output_format=ImplementationPlan)`, real `generate_plan`
   orchestration (metadata stamped by codegraft), `plan --stub` offline mode,
   mocked tests + opt-in live marker. **Done.** `plan` is now real.
5. ✅ **Markdown rendering & request handling** — table-cell escaping, snapshot
   test vs checked-in `examples/sample_plans/add-rbac.md`, title/body ranking-
   signal split for long requests, `inspect --request-file`, 62 tests. **Done.**
   - ✅ Mini-feature: estimated **token savings** (`utils/tokens.py`,
     `RepoAnalysis.token_estimate()`) — shown in `inspect` and plan metadata.
6. ✅ **OpenAI provider** (same `PlanProvider` contract, shared prompt) + `--json`
   + `plans/_debug/<stem>.plan.json` + README/`docs/architecture.md` polish.
   **Done — V1 complete.** Remaining: a live `plan` run with a real key (user).
7. ✅ **Read-side context tools** (`.features/read-side-context-tools.md`) — the
   read-side wins that stay inside codegraft's "what should I look at?" mission,
   pointed backwards. Extracted the import resolver into `repo/imports.py`
   (`build_import_graph`), then built three deterministic, model-free queries that
   surface through the MCP adapter + CLI: `impact_of` (reverse deps / blast
   radius), `get_symbol` (one definition vs a whole-file read), `affected_tests`
   (reverse-closure ∩ tests, **selection only — never runs them**). All three are
   heuristic (a reference scan, not an AST) and stamp `resolution`/`completeness:
   "heuristic"`. Each ships a value validator vs git history — `eval-impact`
   (co-change pair linkage), `eval-symbol` (read-side token savings),
   `eval-tests` (test-selection recall) — mirroring `eval` for ranking. **Done.**

## Scope guardrails — DO NOT build in V1

No embeddings/vector stores/RAG. No tree-sitter / full AST across languages. No
git-diff validation against the plan. No multi-agent planner+reviewer by default.
No SQLite project memory. No remote repo cloning. No web UI or IDE plugin. No
"let codegraft edit code / run Claude Code for you."

(The MCP server was originally out of scope but shipped in Phase 7 as a thin
read-only adapter over the existing `analyze_repo` engine — same core, no new
capability surface. It stays within the "read-side, no editing/execution"
boundary above.)

If an idea doesn't make the **single-run local planning pipeline** noticeably
better, it goes to V2.

## Conventions

- Python 3.11+, `from __future__ import annotations`, full type hints.
- Pydantic v2 models for all structured data. Typer for CLI, Rich for output.
- Cross-platform: this is developed on Windows. Use `pathlib`, pass explicit
  `encoding="utf-8"` on file I/O, and don't assume POSIX-only shell behaviour.
- Secrets come only from env/`.env`; never write or render API keys.
