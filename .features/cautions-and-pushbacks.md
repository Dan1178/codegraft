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
- **Third field gap — feature-specific templates and JSON data fixtures still
  under-rank, even with intent roles ON.** Field note from the oracle-rex
  React/TS migration (Phases 3 & 4, 2026-06-16 — real implementation `select_context`
  runs, not a codegraft eval). With frontend intent the ranker did its job well on
  *code*: each phase's port target and reuse targets came back at or near the top
  (`tactical_calculator.js` #1 then `rules.js`, plus `JobResultView`,
  `advisorSections`/`rulesCard`, `useAiJob`), at ~93–95% token savings. But two
  classes of file the feature genuinely depended on **never made the bounded top
  set**, and had to be opened by hand in both phases:
  (1) the **feature-specific Django template** (`templates/tactical.html`,
  `templates/rules.html`) — needed for the exact markup, icon paths, and tab copy
  to port. The intent fix lifts templates *as a class*, but the single right
  template for the feature still lost to the strong JS/TS symbol matches and fell
  outside the cap.
  (2) **JSON data fixtures** (`core/demo/scenarios/*.json`) — needed for the demo
  wiring (the `unit_counts` keys, the rules-chip shape). These have *no path to
  rank at all*: JSON is in `_NON_CODE_LANGS` (no `symbol` signal) and
  `core/demo/scenarios/` earns no role weight (frontend or backend), so a data
  fixture a frontend feature is built around can only ever score on a bare filename
  match. Candidate refinements (validate each with `eval --ablation`): (a) give
  JSON/data fixtures a lightweight content signal — match request keywords against
  filename + top-level JSON keys — and/or treat `fixtures`/`scenarios`/`data` dirs
  as a rankable (neutral) role; (b) when intent is frontend, give a small targeted
  boost to a template whose name or `{% block %}`/`id=` anchors match request terms,
  so the *specific* feature template surfaces, not just templates generically. Open.
  NB: directional signal from another repo, not a measured eval regression —
  reproduce in the harness (a full-stack fixture with a sibling JSON fixture + a
  feature template) before tuning.
  - **Follow-up (2026-06-16, oracle-rex Phase 5 — Board + Strategy).** A third
    `select_context` run refines (1) and (2) above. The request explicitly named
    the demo ("demo Load Sample Milty Draft Board") — and this time the **JSON
    fixtures _did_ surface** (`core/demo/scenarios/sample_opening_board.json` #8,
    `core/demo/responses/sample_opening_strategy.json` #7), riding a strong
    filename signal (`filename: 18`) once the request keywords matched the file
    *names*. So the JSON gap in (2) is **not absolute** — a data fixture can rank
    when the request names it; it's silent only when the request describes a fixture
    it can't name. The *durable* miss is **CSS**: the request asked to "port the
    hex-grid CSS layout from the legacy style.css", yet `static/css/style.css` —
    the single most important file to port for a board/layout feature — **did not
    appear at all** (nor did the board template). CSS is the blind spot to fix
    next: like HTML it has no symbol signal, and `static/css/` earns the `static`
    frontend role but apparently not enough to clear a 12-file cap dominated by
    JS/TS/Python symbol matches. Candidate: a content signal for stylesheets
    (selector/class-name + custom-property tokens matched against request keywords),
    and/or recognizing an explicit "port `<file>`" mention as a near-direct hit.
    Still directional (a planning run, not an eval); fold into the same harness
    fixture — add a `style.css` the request names explicitly. **Implemented
    2026-06-16** (both candidates shipped together — see
    `css-and-named-fixture-ranking.md`): CSS now earns a `symbol` signal from its
    class/id/custom-property names (always-on, mirroring the template fix), and a
    file the request names outright (`static/css/style.css`) earns a `named_file`
    near-direct-hit boost — extracted from the *full* request, so it survives the
    `ranking_signal` focus that was a second, independent cause of the miss (the
    CSS clause was being truncated away before keyword extraction ever ran).
    Toggleable via `use_named_file_boost` for `eval --ablation`. Covered by unit +
    synthetic-fixture tests; home-repo eval recall-neutral (0.830 on/off, MRR
    +0.033). One step remains — field re-validation on oracle-rex Phase 5.

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
