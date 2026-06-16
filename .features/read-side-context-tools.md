# Feature family: read-side context tools (codegraft enhancements)

**Status: proposed (2026-06-16).** Surfaced from real `select_context` use on the
oracle-rex repo — the read-side wins that are genuinely codegraft-shaped. This
file scopes the in-codegraft work; sibling spin-off tools live in
`.features/spinoffs/`. Full disposition of all nine field proposals is recorded at
the bottom of this file.

## The scoping line (why these three and not the rest)

codegraft answers exactly one question:

> **Given this request and this repo, what should I look at?** — deterministically,
> read-only, no execution, no cross-run memory, single-run.

A proposal belongs in codegraft only if it stays inside that sentence. Anything
that **(a)** executes the project, **(b)** remembers state across runs, **(c)**
reaches outside the repo, or **(d)** needs true language-server semantics is a
different tool. The three features below are the slice that passes; they extend
the existing MCP surface (`select_context` / `generate_plan`) and reuse machinery
codegraft already has (the import-edge graph in `repo/rank.py`, the bounded
snippet extractor in `repo/snippets.py`, the `_SYMBOL_RE` symbol scan).

---

## 1. `impact_of(file)` — reverse-import / dependency lookup

**Build this first.** It is the clearest fit and nearly free.

**Concept.** A deterministic query: "what in this repo depends on `X`?" Given a
file (V1) it returns the set of files that import it, so an agent can answer
"what might break if I change this?" *before* editing — instead of a grep-and-read
loop.

**Why it's in scope.** codegraft already computes forward import edges
(`_referenced_paths`, `_build_path_index`, the import-edge tally that feeds the
`imported_by` ranking signal). A reverse query is the transpose of work already
done on every run — deterministic, read-only, no model call, no per-request cost.
It is the same context-selection mission, simply pointed backwards.

**Shape (sketch).**
```
impact_of(path) -> {
  imported_by: [paths that import `path`],
  resolution: "heuristic",   # honest about precision
}
```

**Boundaries / honest caveats.**
- **Triage-grade, not a guarantee.** codegraft's resolver is deliberately
  lightweight (JS/TS relative + `@/` alias, Python dotted with *unambiguous*
  basename match — it self-describes as "a lightweight reference scan, not an
  AST"). It will miss dynamic imports, re-exports, and ambiguous basenames. Frame
  the result as "what *likely* depends on this," never as a correctness oracle.
- **File-level only.** Symbol-level "what breaks if I change *this signature*"
  needs cross-file type resolution → that's the LSP bridge (`spinoffs/
  code-intelligence-bridge.md`), out of scope here.

**Effort:** small — mostly exposing and inverting an index that already exists.

---

## 2. `get_symbol(name)` — heuristic symbol-granularity fetch

**Concept.** Return just one definition — signature + body + a few lines of
context — instead of making the agent Read a whole file for one function/block.
The single biggest read-side token win observed in the field (whole-file reads of
`style.css`, `app.js`, `tts_string_ingest.py` for one region each).

**Why it's in scope.** This is the existing snippet extractor at finer
granularity: codegraft already has `_SYMBOL_RE` (def/class/func/...) and bounded
snippet logic. "Snippet at symbol granularity" is a natural narrowing of what
codegraft already does — pick the file (ranking), then pick the region.

**Shape (sketch).**
```
get_symbol(name, path=None) -> {
  path, signature, span: [start_line, end_line], snippet, resolution: "heuristic"
}
```

**Boundaries.**
- **Heuristic location only.** It finds the *definition text* by regex/structure,
  within a file (or the ranked candidate set). It does **not** do
  `find_references` or `go_to_definition` — those need real per-language
  resolution (LSP), which is operationally heavy, stateful, and cross-language.
  Those two explicitly belong to `spinoffs/code-intelligence-bridge.md`.
- Precision is "good enough to avoid a full-file read," not compiler-accurate.

**Effort:** small–medium — extends `repo/snippets.py`; needs a name→span locator.

---

## 3. Test-impact *selection* — a by-product of #1, not a new feature

**Concept.** "Which tests are affected by these changed files?" so a loop can run
the relevant handful instead of the whole suite.

**Why it needs almost no new code.** Affected tests are simply
`impact_of(changed_files) ∩ test_paths`. Once #1 exists, this is a thin filter,
not a bespoke capability. codegraft already identifies `test_paths` in
`RepoSummary`.

**Boundaries (be strict here).**
- **Selection only — never execution.** *Running* the selected tests is the
  feedback tool's job (`spinoffs/run-and-filter-feedback-tool.md`), because that
  crosses the "no execution" line. codegraft hands back a list; something else
  runs it.
- **False negatives are the real risk.** A heuristic import graph can omit a test
  that actually breaks. Position this as a fast-feedback *hint* that speeds the
  inner loop — it must never replace a full-suite run before merge.

**Effort:** trivial on top of #1.

---

## Full disposition of the nine field proposals

| # | Proposal | Home |
|---|----------|------|
| 3 | Dependency/impact lookup | **codegraft** (this file, #1) |
| 1 | Symbol-level fetch | **Split** — heuristic `get_symbol` here (#2); `find_references`/`go_to_def` → code-intelligence bridge |
| 5 | Test-impact | **Split** — selection here (#3); running → feedback tool |
| 2 | Delta re-reads | **Harness** (Claude Code) — session state, not a tool |
| 4 | Structured test reporter | Run-and-filter feedback tool |
| 7 | Filtered build/lint deltas | Run-and-filter feedback tool |
| 6 | Structured diff/review | **Existing `/code-review`** — review workflow, not new |
| 8 | Contract/schema index | Cross-stack contract linter |
| 9 | Installed-dep signatures | Code-intelligence bridge |

### Handled elsewhere — not their own product

- **#2 delta re-reads → the harness.** "You read this at vN, here's the diff
  since" is session state. codegraft is single-run and stateless by design (no
  cross-run/project memory). The field note itself observes "the harness already
  tracks file state" — so this is a Claude Code / agent-runtime feature, not a
  context-selection tool.
- **#6 structured diff/review → existing `/code-review`.** Summarizing a git diff
  is a review/PR workflow, which codegraft explicitly excludes (no git-diff work),
  and which `/code-review` already covers. No new repo.

---

# Implementation plans

Three plans, ordered by dependency: build #1 first — #3 is a thin filter on top of
it, and #2 is independent. All three are deterministic, read-only, no model call,
and surface through the existing MCP adapter (`mcp.py`) + the Typer CLI (`cli.py`),
exactly like `select_context` / `inspect`.

## Shared prerequisite — a reusable import index (`repo/imports.py`)

Both #1 and #3 need the repo's import edges over **all** candidate files, not just
the stage-2 top-N that `rank_files` reads today. The resolution logic already
exists but is private to `repo/rank.py`: `_build_path_index`, `_normalize_rel`,
`_match_module`, `_resolve_specifier`, `_referenced_paths`, the import regexes
(`_JS_IMPORT_RE`, `_PY_FROM_RE`, `_PY_IMPORT_RE`), `_JS_EXTS`, `_RESOLVE_EXTS`, and
`_read_head`.

**Step 0 (refactor, do once):** extract those into a new `repo/imports.py` with a
public surface, and re-import them in `rank.py` so its behaviour is unchanged.
This is a pure move — the existing import-edge tests (`test_imported_central_file_is_pulled_in`,
`test_import_edge_can_be_disabled`) are the regression guard; they must stay green
byte-for-byte. Keep the heuristic exactly as-is (the `imported_by` ranking signal
depends on its current precision).

New public function:
```python
def build_import_graph(scan, root, config) -> ImportGraph
# ImportGraph.forward[path]  -> set[paths it imports]      (already computable)
# ImportGraph.reverse[path]  -> set[paths that import it]  (the transpose)
```
It reads each candidate file's head once via `_read_head` (bounded by
`config.repo.max_file_lines`) and resolves references with the existing helpers.
Cost note: this is O(candidates) head-reads vs. `rank_files`' O(stage2_limit).
Acceptable for an on-demand query; document it, and respect `scan.truncated` /
the scale `mode` so a huge repo degrades predictably rather than stalling.

---

## Plan A — `impact_of` (reverse-import / dependency lookup)  ⟵ build first

**Goal.** "What in this repo depends on `X`?" so an agent can gauge blast radius
before editing, instead of a grep-and-read loop.

**Design.**
- New `repo/graph.py` (or fold into `imports.py`): a thin query layer over
  `build_import_graph`.
  ```python
  @dataclass
  class ImpactResult:
      target: str
      imported_by: list[str]      # direct importers, sorted
      transitive: list[str]       # optional: full reverse closure (BFS), V1.1
      resolution: str = "heuristic"
  def impact_of(target, scan, root, config, *, transitive=False) -> ImpactResult
  ```
- V1: **direct importers** (`graph.reverse[target]`). Transitive closure is a
  bounded reverse-BFS — ship it behind a flag once direct is validated.
- Resolve `target` leniently: accept the repo-relative path; if a bare basename is
  given, reuse the `by_basename` index from `_build_path_index` and disambiguate
  (error listing candidates if >1), mirroring how named-file matching already
  handles bare vs. path-qualified mentions.

**Surfaces.**
- MCP: `impact_of(target: str, repo=".", transitive=False)` in `mcp.py`, with a
  matching `impact_of_payload` builder (the testable half, like
  `select_context_payload`). Payload: `{target, imported_by, transitive?, resolution}`.
- CLI: `codegraft impact <path> [--transitive] --repo .` — render importers as a
  short list, echoing the `resolution: heuristic` caveat so the limitation is
  visible at the call site.

**Boundaries baked into the output.** Always stamp `resolution: "heuristic"` and,
in help text, name the known blind spots (dynamic imports, re-exports, ambiguous
basenames). It is blast-radius *triage*, never a correctness oracle.

**Validation.** New `tests/test_graph.py`:
- Reuse `_taxonomy_repo` (three wrappers importing one shared screen): assert
  `impact_of(shared).imported_by` == the three wrappers.
- Python `from a.b import c` and relative JS `./x` edges both invert correctly.
- A file imported by nobody → empty `imported_by` (not an error).
- Ambiguous basename → does **not** smear across same-named files (the existing
  unambiguous-basename rule must hold under the reverse view).
- Refactor guard: `pytest tests/test_rank.py` stays green after Step 0.

**Scope check.** Pure read-only graph query reusing existing machinery — the
read-side mission pointed backwards. In scope. **Effort: small** (mostly Step 0 +
a transpose).

**Files in play.** `repo/imports.py` (new, extracted), `repo/graph.py` (new),
`repo/rank.py` (import from `imports.py`), `mcp.py`, `cli.py`, `tests/test_graph.py`.

---

## Plan B — `get_symbol` (heuristic symbol-granularity fetch)

**Goal.** Return one definition (signature + body + a little context) instead of a
whole-file Read for a single function/block.

**Design.**
- New `repo/symbols.py`. A locator finds where a symbol named `name` is *defined*,
  reusing the existing patterns: `_SYMBOL_RE` (code) and `_TEMPLATE_SYMBOL_RE` /
  `_STYLE_SYMBOL_RE` (HTML/CSS), matching the captured identifier against `name`
  via `split_identifier` equality.
  ```python
  @dataclass
  class SymbolHit:
      path: str
      name: str
      signature: str           # the def/class/selector line, stripped
      span: tuple[int, int]    # 1-based [start, end]
      snippet: str             # rendered with line numbers (reuse snippets._render)
      resolution: str = "heuristic"
  def find_symbol(name, scan, root, config, *, in_path=None) -> list[SymbolHit]
  ```
- **Block-extent heuristic, language-tiered** (the only real complexity):
  - Python: from the `def`/`class` line, consume lines until indentation returns to
    ≤ the definition's indent (the proven, dependency-free approach).
  - Brace languages (JS/TS/Go/…): balance `{`/`}` from the definition line.
  - CSS: consume to the matching `}` of the selector block.
  - Fallback: a fixed window if the language is unknown.
  - Cap the span at `max_snippet_lines_per_file`; set `truncated` if hit.
- Search scope: `in_path` restricts to one file; otherwise scan all candidate
  files and return **all** matches (a name can be defined in several places) sorted
  by path, so the caller disambiguates rather than us guessing.
- Reuse `snippets._render` for numbered output (extract it to a shared spot, or
  import it — keep one renderer).

**Surfaces.**
- MCP: `get_symbol(name: str, repo=".", path=None)` + `get_symbol_payload`.
- CLI: `codegraft symbol <name> [--in <path>] --repo .`.

**Boundaries.** Heuristic *location and extent* only — explicitly **not**
`find_references` / `go_to_definition` (those need real cross-file resolution =
the LSP bridge). Precision target: "good enough to avoid a full-file read."

**Validation.** New `tests/test_symbols.py`:
- Python `def`/`class` block extent (stops at dedent, not EOF).
- JS/TS function block via brace balance.
- CSS selector block extent.
- `name` defined in two files → two `SymbolHit`s returned.
- Unknown name → empty list (not an error). Over-long body → `truncated` set.

**Scope check.** The bounded-snippet extractor at finer granularity — squarely the
read-side mission. In scope. **Effort: small–medium** (the block-extent tiers are
the work).

**Files in play.** `repo/symbols.py` (new), `repo/snippets.py` (share `_render`),
`repo/rank.py` (reuse the symbol regexes — import, don't duplicate), `mcp.py`,
`cli.py`, `tests/test_symbols.py`.

---

## Plan C — test-impact selection (a thin filter on Plan A)

**Goal.** "Which tests are affected by these changed files?" so a loop can run the
relevant handful — *selection only; running stays out* (feedback tool).

**Design.**
- `affected_tests(changed_files)` = the **reverse-reachable closure** of
  `changed_files` over `ImportGraph.reverse`, intersected with the repo's test
  files. Transitive matters here: a test that imports a module that imports the
  changed file must be selected, so this uses reverse-BFS (Plan A's transitive
  helper), not just direct importers.
  ```python
  def affected_tests(changed, scan, summary, root, config) -> AffectedTests
  # .tests: list[str]        (reachable ∩ test files, sorted)
  # .completeness: "heuristic"
  ```
- Identify test files from `RepoSummary.test_paths` (already computed by
  `summarize`); a candidate is a test if its path is under / equals a `test_paths`
  entry — reuse the exact membership check `_stage1_signals` uses for the `test`
  signal so the definition of "a test" stays consistent.

**Surfaces.**
- MCP: `affected_tests(changed_files: list[str], repo=".")` + payload builder.
- CLI: `codegraft affected-tests <files...> --repo .`, optionally `--since <ref>`
  to derive the changed set from git via the existing read-only helper
  `commit_changed_files` in `evaluation.py` (no execution, just `git diff`).

**Boundaries — be strict.** Output carries `completeness: "heuristic"` and the help
text states plainly: **false negatives are possible** (a heuristic graph can omit a
test that truly breaks). This accelerates the inner loop; it must never replace a
full-suite run before merge. *Running* the selected tests is the run-and-filter
feedback tool's job, not codegraft's.

**Validation.** Extend `tests/test_graph.py`:
- A test importing a module that imports the changed file → selected (proves
  transitivity).
- A test importing nothing in the closure → not selected.
- Changed file with no dependent tests → empty list (not an error).

**Scope check.** A filter over Plan A's graph (`reverse-closure ∩ test_paths`) —
selection, not execution. In scope. **Effort: trivial** on top of Plan A.

**Files in play.** `repo/graph.py` (transitive reverse-BFS + test filter),
`mcp.py`, `cli.py`, `tests/test_graph.py`. Reuses `commit_changed_files` for the
optional `--since`.

---

## Cross-cutting open questions

- **Graph build cost on large repos.** `build_import_graph` reads every candidate
  head; `rank_files` only reads stage-2. Confirm acceptable latency on a big repo,
  and decide whether to cache the graph within a single CLI/MCP invocation that
  needs it more than once.
- **Transitive depth for Plan C.** Full closure vs. a bounded depth — full is
  safer (fewer false negatives) but larger; measure on a real repo before capping.
- **Symbol disambiguation UX.** When `get_symbol` finds N definitions, return all
  (current plan) vs. rank by the same relevance heuristics — start with "return
  all," let usage tell us if ranking is worth it.

---

# Adoption: making the new tools actually get used to their fullest

Building the tools is necessary but not sufficient. An MCP tool only earns its
keep if the agent *reaches for it instead of* the built-in habit it replaces —
`impact_of` instead of grep-for-importers, `get_symbol` instead of `Read` a whole
file, `affected_tests` instead of re-running the suite. That is driven almost
entirely by three things: **tool descriptions, the standing usage guidance, and
payload shape.** Below is what has to change beyond the code in the plans above.

## 1. Register the tools on the MCP server (mechanical)

Each tool needs a `@server.tool()` wrapper in `build_server()` plus a
`*_payload` builder (the testable half), mirroring `select_context` /
`generate_plan` exactly. The payload builders hold the logic; the wrappers stay
trivial. No Claude Code client-config change is required — once the server
exposes the tools, they appear after the user updates the installed codegraft and
**restarts the MCP server** (note this in release notes; an already-running server
won't pick up new tools).

## 2. Write trigger-oriented descriptions (the real adoption lever)

The docstring on each `@server.tool()` is the contract the agent reads to decide
*when* to call. `select_context`'s description works because it leads with **"Call
this FIRST … before manually grepping or reading files"** and names the habit it
displaces. The new tools need the same shape — a trigger, the displaced behavior,
the cost story, and the trust caveat. Proposed text:

- **`impact_of`** — *"Call this BEFORE editing a shared file or symbol, instead of
  grepping for who imports it. Returns the files that depend on `target` so you can
  judge blast radius up front. Deterministic, free, no LLM. Resolution is
  heuristic (misses dynamic imports / re-exports) — use it as blast-radius triage,
  not a guarantee."*
- **`get_symbol`** — *"Call this instead of reading a whole file when you need one
  function/class/selector. Returns just that definition + signature + a few lines.
  Free, no LLM. Heuristic location — for exact cross-file resolution use your
  editor's go-to-definition."*
- **`affected_tests`** — *"After editing, call this to get the tests that depend on
  your changed files, so you run the relevant handful first. Selection only — it
  does not run anything, and being heuristic it can miss tests, so run the full
  suite before merging."*

Each description must (a) name the **default behavior it replaces**, (b) state
**free / no-LLM / tiny payload**, and (c) carry the **heuristic caveat** inline so
the agent calibrates trust at the call site rather than over-relying.

## 3. Extend the standing usage guidance (highest-leverage change)

The single biggest behavioral lever is the user-level `~/.claude/CLAUDE.md`
"codegraft — context selection" block, which today only mentions
`select_context`. It should grow into a short **decision tree** covering the whole
read-side loop, so the agent knows which tool fits which moment:

```
## codegraft — read-side tools

- Planning/implementing a feature or change → `select_context` FIRST (ranked
  files + snippets), before grepping/reading.
- About to edit a shared file or symbol → `impact_of` to see what depends on it.
- Need one function/class, not the whole file → `get_symbol`, not Read.
- Just edited files and want fast feedback → `affected_tests` to pick the
  relevant tests (then run them; codegraft does not run them for you).
All are deterministic, need no API key, and cost no request tokens. Skip them
only for trivial changes you can already locate.
```

This is what changes session-to-session behavior. Ship it as a documented,
copy-pasteable snippet in the codegraft README so users adopt the workflow, not
just the binary. (Project-level `CLAUDE.md` in a given repo can reinforce it for
teams.)

## 4. Keep payloads agent-friendly (cheap + trust-calibrating)

MCP results are injected as context tokens, so the same token discipline that
defines `select_context` applies:

- **Minimal structured JSON, not prose.** `impact_of` returns a path list;
  `get_symbol` returns one bounded snippet; `affected_tests` returns a test-path
  list. No rendered tables, no restating the request.
- **Trust flags on every payload.** `resolution: "heuristic"` /
  `completeness: "heuristic"` so the agent knows not to treat results as
  exhaustive — the machine-readable echo of the inline caveats.
- **Compose-forward hints, sparingly.** A field like `next: "get_symbol"` on a
  ranked file, or `affected_tests` accepting the file list a prior call surfaced,
  lets the tools chain without the agent re-deriving inputs. Don't overdo it —
  hints, not orchestration.

## 5. Make the tools compose into one loop

The intended read-side loop is:

```
select_context(request)            # what files matter
  → get_symbol(name, path)         # read only the region you need
  → impact_of(file)                # before you change it, see who breaks
  → (edit)
  → affected_tests(changed_files)  # pick the tests to run first
```

Cross-reference this in each tool's description ("after `select_context`, use
`impact_of` on a file you intend to change") so the agent discovers the chain from
any entry point, and surface it once in the README as the canonical flow.

## 6. Guard against misuse and spin

`impact_of` / `affected_tests` build the import graph over **all** candidate files
(§"Shared prerequisite"), which is heavier than `select_context`'s stage-2 reads.
To keep them from feeling like they "spin":

- State in the description that they are **single-shot, bounded** (respect
  `max_file_lines` / scale `mode`), not background indexers.
- Tell the agent **when not to call**: trivial single-file edits, or a file the
  agent already knows is a leaf. The "skip for trivial changes" line in the
  guidance covers this.
- If graph latency is noticeable on large repos, cache it within a single
  invocation (see open questions) so a `impact_of` + `affected_tests` pair in one
  turn builds the graph once.
