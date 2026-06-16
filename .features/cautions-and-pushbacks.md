# Cautions & pushbacks (carry across sessions)

My standing concerns on the CodeGraft blueprint. None of these are objections to
building it — they're where attention/iteration budget should go, and the
assumptions to verify rather than trust. Update as items are resolved.

## 1. Ranking quality is the whole ballgame
**Status: open — the core risk.**

Discovery, ignore, and safety filtering are plumbing you get right in an
afternoon. The project succeeds or fails on **relevant-file ranking**. Pure
lexical overlap is naive: "add RBAC" will match every file containing "user".

- Budget most of the *iteration* time here, not on the scanner.
- Lean hard on `inspect` as the debugging surface — show scores so weak ranking
  is visible and tunable.
- When ranking feels bad, fix heuristics + debug output **before** reaching for
  LLM reranking or embeddings (the latter is explicitly out of V1 scope).
- **Concrete gap found in the field** (see `experiment-meshimate-ab.md`): the
  most central file to a task can be missed when it's the *shared* dependency the
  request keywords don't name (the wrapper screens ranked; the
  `TaxonomyManagementScreen` they all import did not). Candidate fix: an
  **import-graph proximity boost** — if several top-ranked files import X, pull X
  into the bundle. Open.
- **Second field gap — role weights are server-side-only, so frontend targets
  under-rank in full-stack repos.** On a `select_context` for a *frontend* request
  ("migrate the plain-JS frontend to React/TS; find templates, JS files, API
  calls") in a Django-dominant repo (oracle-rex), the top 12 came back ~10/12
  **backend** Python (AI service, schemas, models, migrations, constants, tests);
  only `app.js` (#3) and one template (#9) were frontend. Root cause is structural,
  not lexical: `_ROLE_WEIGHTS` in `rank.py` is entirely server-side vocabulary
  (`routes/controllers/handlers/endpoints/api/views/services/models/schemas/
  migrations/auth/core`) with **no** frontend roles — so in a full-stack repo every
  backend file earns a `role` bump (the visible `role: 4` does much of the work)
  that `templates/` and `static/js/` *cannot earn*, even when the request explicitly
  names the frontend. Compounding it: HTML is in `_NON_CODE_LANGS`, so templates get
  no `symbol` signal either. Candidate fixes (validate each with `eval --ablation` —
  adding roles risks regressing backend-targeted queries): (a) add frontend role
  segments (`components`, `pages`, `hooks`, `features`, `templates`, `static`, `ui`,
  `styles`, `store`/`stores`, `composables`); (b) bigger lever, likely V2 — let
  *intent* keywords in the request (`react`, `frontend`, `typescript`/`tsx`, `css`,
  `template`, `component`) modulate which role weights apply, so a frontend request
  down-weights backend roles instead of competing with them flat. Open. NB: this was
  a planning task in *another* repo, not a codegraft eval — treat as a directional
  signal to reproduce in the harness, not a measured regression. **Implemented
  2026-06-15** (both fixes (a)+(b) shipped together — see
  `intent-aware-role-weighting.md`): `request_intent` modulates split
  backend/frontend/neutral role weights, gated to preserve a byte-for-byte no-op
  when the request has no clear lean; templates now earn a symbol signal. Covered
  by unit + synthetic-fixture tests, and **field-validated on oracle-rex
  (2026-06-16)**: the original failing frontend request went from **2/12 → 10/12
  frontend files** in the top-12 with the lever on (OFF reproduces the failure
  exactly). Largely closed; one tuning thread remains — the `0.4` backend
  down-weight is a touch aggressive (starves a frontend request's secondary "API
  calls" sub-goal), best set against a full-stack eval fixture. See
  `intent-aware-role-weighting.md` for the run and observations.

## 2. The `ImplementationPlan` schema is large (15 fields, nested)
**Status: MATERIALIZED then RESOLVED.**

This is exactly what I worried about. On the user's first live Anthropic run, the
schema was too complex for grammar-constrained structured outputs:
`400 invalid_request_error: "Grammar compilation timed out."` — the structured-
output engine compiles the JSON schema into a decoding grammar up front, and our
schema is big enough to time that out.

**Fix:** the Anthropic provider switched from `messages.parse` (grammar-
constrained) to **instructed JSON + Pydantic validation** — embed the schema in
the prompt (~1.9k tokens, `metadata` stripped), call `messages.create`, then
`ImplementationPlan.model_validate_json()` on the extracted object. No grammar
compilation, so the error cannot recur. The typed contract (the real value) is
preserved. Also bumped `max_output_tokens` 8000→12000 (JSON is more verbose than
prose) and raise a clear error on `stop_reason == "max_tokens"`. OpenAI still
uses `chat.completions.parse` (its engine handles the schema). `live_anthropic`
smoke test exercises the real path. (This is the fallback caution #3 anticipated.)

## 3. The ChatGPT research citations are unverifiable
**Status: RESOLVED (Phase 4).**

The load-bearing claim — "Anthropic supports schema-constrained structured
outputs" — was **confirmed** against the authoritative claude-api skill: real
support via `client.messages.parse(output_format=<Pydantic model>)` →
`.parsed_output`. No JSON-mode fallback was needed; the architecture held.

Implementation note: the strict schema forces the model to emit all fields,
including `metadata` — so codegraft **overwrites** `plan.metadata` after parsing
(the model is told to leave it empty, but provenance is authored by us
regardless). Other ChatGPT citations remain unverified but are non-load-bearing.

## 4. Windows / cross-platform reality
**Status: partially handled — stay vigilant.**

Already bit us in Phase 1: the legacy Windows console (cp1252) crashed on
`->`/`—` glyphs and would crash on any non-ASCII model output via `--stdout`.
Fixed by forcing UTF-8 streams + keeping our own console literals ASCII.

Remaining watch items:
- `git ls-files` subprocess calls: handle the `-z` NUL separator, `--full-name`
  paths, and decode as UTF-8 explicitly.
- Always pass `encoding="utf-8"` on file I/O (plans, snippets, config).
- Use `pathlib` everywhere; normalize separators when matching ignore patterns
  (PathSpec expects forward slashes).
- Don't assume POSIX-only shell behaviour anywhere in the pipeline.

## 5. Scope discipline is the report's best quality — protect it
**Status: ongoing.**

The blueprint is unusually disciplined; the failure mode is letting it drift
toward embeddings, tree-sitter project maps, diff validation, multi-agent
orchestration, or a web UI. The guardrails live in `CLAUDE.md`. Rule of thumb:
if an idea doesn't make the **single-run local planning pipeline** noticeably
better, it's V2.
