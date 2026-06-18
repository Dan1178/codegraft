# Improvement notes — `affected_tests`

Notes from a real-world miss observed using `affected_tests` on a Django + React/TS
repo (oracle-rex, 2026-06-16). Captured here so the fix and the follow-ups don't
get lost. The headline finding is small and high-impact: **the test-path
classifier doesn't recognize `.test.tsx` / `.spec.tsx` files**, so React component
tests are silently dropped from selection.

> **Status (2026-06-16): primary fix #1 + regression tests #2 implemented.**
> `find_test_paths` now matches the `.test`/`.spec` infix against the JS/TS
> extension set (`detect._is_js_ts_test`); regression cases added in
> `tests/test_detect.py` and `tests/test_graph.py`; full suite green (134 passed).
> Verified end-to-end against oracle-rex: the 5-file change that previously
> selected 1 test now selects all 7 reverse-reachable tests. The "secondary
> impact" (ranking `test` signal) is fixed by the same change. The
> "lower-priority follow-ups" below remain open.

## What was observed

Calling `affected_tests` with five changed files:

```
frontend/src/components/Board/Board.tsx
frontend/src/components/UnitCounter/UnitCounter.tsx
frontend/src/features/tacticalMove/MovePanel.tsx
frontend/src/App.tsx
frontend/src/features/fleetManager/fleetModel.ts
```

returned only:

```
frontend/src/features/fleetManager/fleetModel.test.ts
```

It missed `Board.test.tsx`, `App.test.tsx`, `MovePanel.test.tsx` (and
`BattleCalculator.test.tsx`, which imports the changed `UnitCounter.tsx`) — all of
which directly import a changed file and should have been selected. The one test it
did return is the only `.test.ts` (no `x`) in the set.

## Root cause (diagnosed, not guessed)

It is **not** truncation and **not** the import graph. Reproduced against the repo
with codegraft's own code (`discover_repo` → `build_import_graph` →
`affected_tests`, `Config()` defaults):

- `scan.files` = 201, `truncated = False` — every test file is in the scan.
- The reverse edges are present and correct, e.g.:
  - `importers_of("…/Board/Board.tsx")` → includes `…/Board/Board.test.tsx`
  - `importers_of("…/App.tsx")` → includes `…/App.test.tsx`
- So `reverse_closure(...)` *does* contain `Board.test.tsx`, `App.test.tsx`,
  `MovePanel.test.tsx`. They are then dropped by the final filter in
  `affected_tests` (`repo/graph.py`):

  ```python
  tests = sorted(p for p in reachable if _is_test_path(p, test_paths))
  ```

  because they are **not in `test_paths`**.

`test_paths` comes from `detect.find_test_paths` (`repo/detect.py`):

```python
is_test = (
    any(seg in {"tests", "test", "__tests__", "spec"} for seg in segments)
    or base.startswith("test_")
    or base.endswith(("_test.go", "_test.py", ".test.ts", ".test.js", ".spec.ts"))
)
```

The suffix tuple has `.test.ts`, `.test.js`, `.spec.ts` but **omits `.test.tsx`,
`.spec.tsx`, `.spec.js`, and the `.jsx` variants**. React/TS projects put most
component tests in `*.test.tsx`, so on a typical frontend codebase the classifier
recognizes a minority of the test suite. `fleetModel.test.ts` matched `.test.ts`
and survived; every `.test.tsx` was invisible.

## Recommended fix

### 1. Recognize the full JS/TS test-file matrix (primary, ~1 line)

Replace the hard-coded suffix tuple with one that covers `test`/`spec` × the JS/TS
extensions. Minimal version:

```python
base.endswith((
    "_test.go", "_test.py",
    ".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".test.mjs", ".test.cjs",
    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx", ".spec.mjs", ".spec.cjs",
))
```

More robust (don't enumerate — match the `.test.`/`.spec.` infix before any JS/TS
extension, reusing `imports._JS_EXTS`):

```python
stem, _, ext = base.rpartition(".")
is_js_test = ext in _JS_EXTS and (stem.endswith(".test") or stem.endswith(".spec"))
```

This keeps the classifier in step with the extensions the resolver already
understands (`imports._RESOLVE_EXTS`), so "what resolves as a module" and "what
counts as a test" can't drift apart.

### 2. Add a regression case

`tests/test_graph.py` should assert that a `*.test.tsx` importing a changed `*.tsx`
is selected. A matching case in `evaluation_graph.run_tests_eval` (it already
measures recall against history) would have caught this on any React repo in the
eval corpus — the current corpus likely skews Python/`.ts`, which is why the gap
went unmeasured.

## Secondary impact: ranking, not just selection

`graph._is_test_path` is documented to match `rank._stage1_signals`' `test`
signal "exactly," and both derive from `find_test_paths`. So the same omission
means `.test.tsx` files are also **not getting the `test` ranking signal** — they
're under-weighted in `select_context` results on frontend repos, not only missed
by `affected_tests`. One fix in `find_test_paths` corrects both.

## Lower-priority follow-ups for `affected_tests`

These are genuine heuristic limits (correctly stamped `completeness: "heuristic"`),
not bugs — worth noting for the docstring / future work:

- **Co-located non-importing tests.** A test that exercises a module without a
  static import (e.g. via a shared fixture, a barrel, or runtime wiring) won't be
  in the reverse closure. A cheap, high-precision augmentation: also select a test
  whose path is a sibling/`__tests__` neighbor of a changed file sharing its stem
  (`Foo.tsx` → `Foo.test.tsx`, `__tests__/Foo.test.tsx`). This is the "name
  convention" half of test selection that the import graph alone can't see.
- **Re-export / barrel hops.** Already a documented blind spot of the resolver;
  flagged here only because tests frequently import through an `index.ts` barrel,
  which makes the false-negative risk concentrate exactly on test edges.
- **Surface the distinction in output.** Consider returning *why* a test was
  selected (direct importer vs. transitive vs. name-convention) so the caller can
  judge confidence — cheap, and reinforces the "triage, not oracle" framing.

## Suggested priority

1. Fix `find_test_paths` extensions (one line; fixes both selection and ranking on
   every JS/TS frontend repo). 
2. Add the regression test + a React case to the tests eval.
3. Consider the name-convention augmentation for co-located tests.
