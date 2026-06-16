# Feature: intent-aware role weighting (fix frontend under-ranking)

**Status: implemented (2026-06-15).** All three legs of the validation plan land
in `tests/test_rank.py` + `tests/test_text.py`; full suite green (95 passed).
Motivated by a field failure on the oracle-rex
repo (a Django-dominant full-stack app). See `cautions-and-pushbacks.md` §1, the
"second field gap" note. This doc is the diagnosis + plan that note pointed at.

## The failure

A `select_context` for an explicitly *frontend* request — "migrate the plain-JS
frontend to React/TS; find templates, JS files, API calls" — run against
oracle-rex returned a top-12 that was ~10/12 **backend** Python (AI service,
schemas, models, migrations, constants, tests). Only `app.js` (#3) and one
template (#9) were frontend. The request named the frontend explicitly and the
ranker still buried it.

## Diagnosis (root cause is structural, not lexical)

Three mechanisms, in order of impact:

1. **Asymmetric structural bump — the headline.** `_ROLE_WEIGHTS` in
   `repo/rank.py` is 100% backend vocabulary
   (`routes/controllers/handlers/endpoints/api/views/services/models/schemas/
   migrations/auth/core`). `_stage1_signals` sums it over every path segment, so
   in a full-stack repo **every backend file earns role 2.5–4.0 before a single
   keyword matches**, while `static/js/`, `templates/`, `components/` earn `0` —
   structurally, regardless of the request. A frontend file must win on
   keyword/symbol signals alone against a flat backend head start. The visible
   `role: 4` does much of the damage.

2. **Templates also lose the symbol signal.** `HTML`/`CSS` are in
   `_NON_CODE_LANGS`, so `_stage2_signals` skips symbol scoring for them.
   `W_SYMBOL` (4.0) is the single largest content weight, and Django templates —
   the *most* distinctively frontend file type — can never earn it.

3. **The one frontend win was accidental.** `app.js` ranked #3 only because it is
   a hardcoded entry-point basename (`W_ENTRY` 2.0 in `repo/detect.py`), not
   because the ranker understood frontend intent. Nothing generalizes from it.

**Why intent doesn't save it today:** keyword extraction (`utils/text.py`) is
flat. `react`/`frontend`/`typescript`/`template` become ordinary content
keywords; they do **not** change *which structural weights apply*. A frontend
request and a backend request rank the structural layer identically, and backend
always has the head start.

**Validation caveat (load-bearing):** codegraft's own repo has no frontend, so
`codegraft eval` against its git history **cannot reproduce or measure this
class of bug**. The harness is real but blind here. The fix needs the dedicated
validation strategy below, not just an eval delta.

## Solution: intent-aware role weighting

Design principle, and the answer to the regression risk: **modulate, don't
flat-add.** The change must be a *strict no-op when no frontend/backend intent is
detected*, so backend-targeted queries (and codegraft's own eval history) see
byte-for-byte identical rankings. Flat-adding frontend roles would instead make
every full-stack repo bump frontend dirs unconditionally and risk regressing
backend-targeted queries.

### 1. Tag the role vocabulary by side

Split `_ROLE_WEIGHTS` into `backend`, `frontend`, `neutral` groups:

- **Frontend (new):** `components`/`component`, `pages`/`page`, `hooks`,
  `composables`, `features`, `templates`/`template`, `static`, `assets`,
  `styles`, `ui`, `widgets`, `screens`, `store`/`stores`.
- **Backend:** the existing entries.
- **Neutral:** `core`, plus `views`/`view`. `views` is genuinely ambiguous
  (Django backend `views.py` vs Vue `views/`), so it is **neutral** rather than
  backend-leaning. Neutral roles keep their weight but are **not** modulated by
  intent (×1.0 always). Honest tradeoff: a frontend request will no longer
  down-weight Django `views.py`, so on Django repos like oracle-rex those files
  can still rank — but we avoid wrongly penalizing Vue `views/`. Net: the fix
  leans on the other backend segments (`api`, `services`, `models`, `schemas`,
  `migrations`) to do the down-weighting work.

### 2. Detect request intent

A small lexicon check over the extracted keywords:

- **Frontend-leaning:** `react`, `frontend`, `tsx`, `jsx`, `css`, `scss`,
  `tailwind`, `component`, `template`, `ui`, `vue`, `svelte`, `style`, `html`,
  `typescript`.
- **Backend-leaning:** `endpoint`, `route`, `migration`, `schema`, `orm`,
  `query`, `auth`, `backend`, `server`, `database`.
- **Outcome:** `frontend`, `backend`, or `none` — where neither firing, *or both*
  firing (mixed), collapses to `none`.

### 3. Apply intent as a multiplier on each role's contribution

| Request intent   | backend role × | frontend role × |
|------------------|----------------|-----------------|
| `none` (default) | 1.0            | **0 (silent)**  |
| frontend         | 0.4            | 1.0             |
| backend          | 1.0            | 0.4             |

**As implemented (refines the original draft):** frontend roles are *gated on*
only by a frontend-leaning request. They are **silent at `none`** — not applied
at ×1.0 — because today's ranker has no frontend vocabulary at all, so applying
new frontend weights to a no-lean request would change rankings and break the
no-op guarantee. The combined `backend ∪ neutral` vocabulary at `none` is
byte-for-byte the legacy `_ROLE_WEIGHTS`, so a no-lean request ranks exactly as
before. Backend roles down-weight (not zero) on a frontend request so a frontend
task that genuinely needs an API file can still surface it via keyword/symbol
signals. `views`/`view`/`core` are **neutral**: never modulated.

The down-weight factor is `ROLE_OPPOSING_INTENT_FACTOR = 0.4`, a named constant;
it needs tuning once a full-stack eval fixture exists (see open questions).

Surface intent + the applied multiplier in the `signals` breakdown so `inspect`
stays debuggable.

### 4. Give templates a content signal

Drop `HTML` from `_NON_CODE_LANGS` *for symbol scoring only*, or add a
lightweight frontend-symbol regex (template `{% block %}` names, `id=`/`class=`
anchors, inline `<script>` identifiers). Shipped **together** with the role fix
in this feature (not split out) — they address the same gap from two angles.

## Validation plan

Because the eval harness is blind to this bug, validation has three legs:

1. **No-op guarantee (unit test):** for a backend-only request with no intent
   keywords, assert the full ranking is *identical* with the feature on vs. off.
   This is the guardrail against backend-query regressions.
2. **New ablation toggle:** plumb `use_intent_roles` through `AnalysisConfig`,
   `run_eval`, and `eval --ablation`, mirroring the existing `use_import_edge`
   pattern (`config.py`, `evaluation.py`). Lets a future full-stack test repo
   measure the delta the way import-edge was measured.
3. **Synthetic fixture test:** a tiny full-stack tree (`static/js/app.js`,
   `templates/index.html`, `services/ai.py`, `models/record.py`,
   `migrations/...`) + a frontend request → assert frontend files rank above
   backend; the *inverse* (lever off) reproduces the backend bias.

**Done.** Legs map to `test_no_intent_request_is_noop`,
`test_frontend_request_lifts_frontend_over_backend`,
`test_intent_roles_off_reproduces_backend_bias`,
`test_template_earns_symbol_signal`, plus `request_intent` unit tests in
`test_text.py`. Home-repo sanity (`eval --last 8`, no frontend): recall@10
identical on/off (0.562), MRR +0.013 with intent on — recall-neutral as expected;
a real measurement needs a full-stack repo.

## Scope check

Heuristic tuning of the existing explainable ranker — squarely in V1 scope. No
embeddings, no AST, no new deps. Keeps the `signals` breakdown debuggable via
`inspect`.

## Open questions

- **Down-weight factor:** 0.4 is a guess. Keep it a named constant; tune once a
  full-stack fixture exists.

## Decided

- **Scope:** role fix + template-symbol fix ship **together** as one feature.
- **`views`:** treated as **neutral** (not modulated by intent) — ambiguous
  between Django backend and Vue frontend.

## Files in play

- `src/codegraft/repo/rank.py` — `_ROLE_WEIGHTS`, `_stage1_signals`,
  `_NON_CODE_LANGS`, `_stage2_signals`.
- `src/codegraft/utils/text.py` — intent lexicon / detection helper.
- `src/codegraft/config.py` — `use_intent_roles` toggle.
- `src/codegraft/evaluation.py` — thread the toggle through `run_eval`.
- `src/codegraft/cli.py` — `eval --ablation` wiring (verify flag surface).
- Tests — no-op guarantee + synthetic full-stack fixture.
