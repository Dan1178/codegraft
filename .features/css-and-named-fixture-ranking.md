# Feature: stylesheet content signal + explicit named-file hit

**Status: implemented (2026-06-16).** Both legs shipped; full suite green (102
passed, 1 skipped). Home-repo sanity (`eval --last 20 --k 12`, no CSS/frontend):
Recall@12 identical on/off (0.830), MRR +0.033 with the named-file boost on —
recall-neutral as expected, since a real measurement needs a full-stack repo.
**Field re-validation on oracle-rex is the remaining step (see below).** Drafted
from the oracle-rex field runs recorded
in `cautions-and-pushbacks.md` §1, the "third field gap" note and its Phase 5
follow-up. This is the diagnosis + plan that note points at ("CSS is the blind
spot to fix next"). Sibling of `intent-aware-role-weighting.md` — same explainable
ranker, same `eval --ablation` discipline, same harness-blindness caveat.

## The failure

oracle-rex Phase 5 (Board + Strategy port), a real implementation `select_context`
run. The request explicitly said to *"port the hex-grid CSS layout from the legacy
`static/css/style.css`."* That file is the single most important file to open for
a board/layout port — and it **did not appear in the top-12 at all** (nor did the
board template). Meanwhile the same run surfaced the JSON demo fixtures fine,
because the request named them by filename and they rode a strong `filename`
signal once the keywords matched the file *names*.

Two earlier phases (notes #1 / #2) show the same shape from the other side: a
feature-specific Django template (`templates/tactical.html`) and a JSON data
fixture (`core/demo/scenarios/*.json`) that the feature was built around had to be
opened by hand because they fell outside the bounded top set — even though the
intent fix lifts templates *as a class*.

## Diagnosis (two independent causes)

### Cause 1 — CSS has no content signal, so it can't compete on content

`CSS` is in `_NON_CODE_LANGS` (`repo/rank.py:34`), so `_stage2_signals` skips
symbol scoring for it — exactly the gap the template fix closed for HTML, but CSS
was never given the equivalent branch. `W_SYMBOL` (4.0) is the single largest
content weight. A stylesheet can therefore only ever score on `filename` / `path`
/ `role` plus a weak `content` signal (`W_CONTENT_HIT` 0.4, capped at 4.8 total),
so on a board feature it loses to JS/TS/Python files that each earn 4.0 *per*
matched symbol. `static/css/` earns the `static` frontend role (2.0) under intent,
but that alone does not clear a 12-file cap dominated by symbol matches. This is
the same structural denial the intent doc identified for templates — CSS is the
file type left behind.

### Cause 2 — the named file is truncated away before ranking even starts

`analyze_repo` calls `ranking_signal(request)` to focus long requests *before*
handing the text to `rank_files` (`repo/analyze.py:60-63`). For a long,
multi-clause request, `ranking_signal` keeps only the leading heading / first line
/ first sentence (`utils/text.py:101`). So the clause naming `style.css` can be
**dropped before keyword extraction** — `style`/`css`/`hex`/`grid` never become
keywords, and the explicitly-named file gets no `filename` hit. This is why a file
the user named in plain English can score zero. It also explains the asymmetry in
the field notes: the JSON fixtures surfaced when their names happened to live in
the part of the request that survived truncation; `style.css` did not.

**Why the existing fixes don't save it:** intent roles lift `static/` as a class
but not the *one* right stylesheet over strong symbol matches; the template-symbol
fix is HTML-only; and neither addresses truncation. The named file needs a path
that does not depend on surviving `ranking_signal`.

## Solution (two legs, shipped together)

Design principle, carried over from the intent fix: **strict no-op when neither
leg fires.** With the toggle off — or a request that names no file and touches no
CSS that reaches stage 2 — rankings are byte-for-byte identical to today.

### Leg A — stylesheet symbol signal (structural parity with templates)

Give CSS the same kind of `symbol` signal HTML templates now get. Add a
`_STYLE_SYMBOL_RE` that extracts the *request-nameable* names in a stylesheet and
nothing else (avoid scoring every property/value as noise, the way
`_TEMPLATE_SYMBOL_RE` avoids plain `<div>`):

- **class selectors** — `.hex-grid` → `hex grid`
- **id selectors** — `#board`
- **custom properties** — `--hex-size` → `hex size`

In `_stage2_signals`, add a branch mirroring the HTML one:

```python
elif detect.language_of(rel_path) == "CSS":
    for cls, idsel, prop in _STYLE_SYMBOL_RE.findall(text):
        symbol_tokens.update(split_identifier(cls or idsel or prop))
```

`split_identifier` already lowercases and splits on `-`/`_`/camelCase, so
`hex-grid` lines up with the `hex` / `grid` request keywords. CSS stays in
`_NON_CODE_LANGS` for everything else (it is still not "code"); this is a
scoped carve-out for symbol scoring only, exactly as HTML was handled.

*Reaches stage 2?* Yes in the motivating case: `static/css/style.css` earns the
`static` role (2.0) plus a `filename` hit on `style`/`css` once Leg B keeps those
keywords alive, so it clears the stage-2 read cutoff (top `_STAGE2_LIMIT`). Leg A
without Leg B is weaker, because a truncated request may strip the CSS keywords —
which is why both legs ship together.

### Leg B — explicit named-file direct hit (also fixes notes #1 / #2)

When the request names a concrete file, that file should be a near-direct hit
regardless of role, symbol, or truncation. Extract filename/path mentions from the
**full** request (not the truncated signal) and pass them into `rank_files`:

- New helper `extract_named_files(request) -> set[str]` in `utils/text.py`: match
  `\b[\w./-]+\.<ext>\b` where `<ext>` is in a known allowlist (reuse the
  `detect._EXT_LANG` keys — `css`, `html`, `js`, `ts`, `tsx`, `json`, `py`, …).
  The extension gate keeps prose like "version 2.0" from matching. Return both the
  bare basename (`style.css`) and any path-qualified form (`static/css/style.css`).
- `analyze_repo` computes `named = extract_named_files(request)` from the **full**
  `request` (before `ranking_signal`) and threads it into `rank_files`.
- `_stage1_signals` adds a `named_file` signal: if a candidate's basename matches a
  bare mention, or its path ends with a slash-qualified mention, award
  `W_NAMED_FILE` (proposed 8.0 — a hair above a single `filename` hit so an
  explicitly named file reliably clears the cap, tuned against the fixture). Stage
  1 placement means it also pulls the file into the stage-2 read set, so Leg A can
  then add the CSS symbol signal on top.

This leg is general: it lifts the named CSS (Phase 5), the named feature template
(note #1), and the named JSON fixture (note #2) by the same mechanism — the
field's recurring observation that "a fixture surfaces when the request names it"
becomes a guarantee instead of an accident.

**As shipped (refines the draft):** the CSS symbol signal (Leg A) ships
*always-on*, exactly like the template-symbol signal it mirrors — it is purely
additive (it only ever adds a `symbol` signal to a CSS file whose selector/
custom-property names match request keywords) and never touches non-CSS files, so
there is no "off" state to guard. Only the named-file boost (Leg B) gets a toggle,
`use_named_file_boost`, since that is the leg with a meaningful no-op contract. In
practice the two legs cover different scenarios: Leg A lifts a stylesheet when the
request's CSS terms *survive* focusing (a short, on-topic request); Leg B lifts an
explicitly-named file when the mention is *truncated away* (a long request). The
fixture tests exercise each independently.

### Not in this feature (deferred)

The notes' candidate of a generic *content* signal for JSON/data fixtures
(matching request keywords against top-level JSON keys) and a rankable
`fixtures`/`scenarios`/`data` role. Phase 5 showed JSON already ranks when named,
and Leg B covers the named case cleanly; a blind content signal for unnamed data
fixtures is a larger, lower-confidence change. Keep it as a separate V2 note unless
a fixture re-run shows the named-file path is insufficient. Out of scope per the
same discipline that kept embeddings/AST out of V1.

## Validation plan

The harness is **blind to this class of bug**: codegraft's own repo has no CSS and
no frontend, so `codegraft eval` against its git history cannot reproduce or
measure it (same caveat as the intent fix). Validation therefore has three legs:

1. **No-op guarantee (unit test):** a backend request that names no file ranks
   byte-for-byte identical with the toggle on vs. off — the regression guardrail.
2. **Ablation toggle:** plumb `use_named_file_boost` (covering both legs, or split
   if useful) through `AnalysisConfig`, `run_eval`, `EvalReport`, and
   `eval --ablation`, mirroring `use_intent_roles` / `use_import_edge`
   (`config.py`, `evaluation.py`, `cli.py`). Lets a future full-stack fixture
   measure the delta.
3. **Synthetic full-stack fixture test:** a tiny tree —
   `static/css/style.css` (with `.hex-grid` / `--hex-size`), `templates/board.html`,
   `core/demo/scenarios/board.json`, plus competing `static/js/board.js` and a
   couple of backend files — and a long, multi-clause request whose first sentence
   is about the board demo and whose *later* clause says "port the hex-grid layout
   from `static/css/style.css`". Assert: with the feature on, `style.css` ranks in
   the top-k and the named template/fixture surface; with it off (and truncation
   active) `style.css` is absent — reproducing the field miss. Add a
   `extract_named_files` unit test in `test_text.py` (allowlist gating, basename vs.
   path-qualified, prose false-positives rejected).

**Done.** Legs map to `test_stylesheet_earns_symbol_signal` (Leg A),
`test_named_file_surfaces_despite_truncation` (Leg B headline — names the file in
a long request whose first sentence truncates the mention out; OFF drops the file
entirely), `test_named_file_boost_can_be_disabled` (ablation), and
`test_named_file_noop_when_nothing_named` (no-op guardrail), plus
`extract_named_files` unit tests in `test_text.py`.

**Field re-validation (remaining):** re-run the oracle-rex Phase 5 request via
`analyze_repo`, A/B on `use_named_file_boost`, and record the before/after top-12
here (target: `static/css/style.css` and the board template enter the top set with
the feature on; OFF reproduces the miss). Directional like the intent run, not an
eval number.

## Scope check

Heuristic tuning of the existing explainable ranker — squarely V1. No embeddings,
no AST, no new deps. New signals appear in the `signals` breakdown so `inspect`
stays debuggable. Symmetric with the template-symbol and intent-role fixes.

## Open questions

- **`W_NAMED_FILE` magnitude (8.0 guess).** Strong enough to clear the cap, not so
  strong it evicts genuine reuse targets the user *didn't* name. Tune against the
  fixture; keep it a named constant.
- **Path-qualified matching.** Suffix-match (`endswith(mention)`) vs. exact — pick
  suffix so `static/css/style.css` in the request matches the candidate path even
  if the repo root differs. Confirm no smearing across same-named files.
- **One toggle or two?** A single `use_named_file_boost` is simplest; split into
  `use_style_symbol` + `use_named_file` only if the ablation needs to isolate the
  CSS-symbol leg from the named-file leg.

## Files in play

- `src/codegraft/repo/rank.py` — `_STYLE_SYMBOL_RE`, CSS branch in
  `_stage2_signals`, `W_NAMED_FILE` + `named_file` signal in `_stage1_signals`,
  `rank_files` signature (accept `named_files`).
- `src/codegraft/utils/text.py` — `extract_named_files` helper.
- `src/codegraft/repo/analyze.py` — extract named files from the **full** request,
  thread into `rank_files`.
- `src/codegraft/repo/detect.py` — reuse `_EXT_LANG` keys for the extension
  allowlist (no change, or expose a small accessor).
- `src/codegraft/config.py`, `evaluation.py`, `cli.py` — `use_named_file_boost`
  toggle + `eval --ablation` wiring.
- Tests — `test_rank.py` (no-op + synthetic fixture, on/off), `test_text.py`
  (`extract_named_files`).
