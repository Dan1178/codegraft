# codegraft — test & quality plan

A practical guide to (1) how the pieces fit together, (2) how to tell whether the
output is any good, and (3) a layered, gated testing plan. Designed to stay
manageable: most gates are already automated; the rest are quick manual checks.

Current status: **62 automated tests passing, 1 opt-in live test.** Run them with
`pytest` from the repo root (or `.\.venv\Scripts\python.exe -m pytest`).

---

## 1. How the components work

codegraft is a pipeline. Everything up to the provider call is **deterministic**
(no model, fully testable); only one step is an LLM call; rendering is
deterministic again.

```
request + repo
   │
   ▼
CLI (cli.py) ── config (config.py: codegraft.toml + .env secrets)
   │
   ▼  DETERMINISTIC ANALYSIS  (repo/analyze.py orchestrates)
   ├─ discover (repo/discover.py)
   │    ├─ git_scan.py    git ls-files: tracked + untracked, labelled
   │    ├─ ignore.py      filesystem fallback w/ nested .gitignore (PathSpec)
   │    └─ safety.py      deny secrets/keys/binaries/oversized/generated
   ├─ summarize (repo/summarize.py)
   │    ├─ tree.py        compact depth-limited directory tree
   │    └─ detect.py      language / framework / manifest / entry-point / tests
   ├─ rank (repo/rank.py) two-stage, explainable score per file
   │    └─ uses utils/text.ranking_signal() to focus long requests
   └─ snippets (repo/snippets.py)  header + keyword windows, under budget
   │
   ▼  PlanningRequest (providers/base.py) — the evidence bundle
   │
   ▼  PROVIDER (the one LLM call)
   ├─ prompt.py            system prompt (package resource) + XML user message
   └─ anthropic_provider.py  messages.parse(output_format=ImplementationPlan)
   │
   ▼  ImplementationPlan (models/plan.py) — validated Pydantic object
   │     (planning/service.py stamps metadata; model never authors it)
   ▼  RENDER (planning/renderer.py) — stable Markdown, every section always present
   │
   ▼  plans/<date>-<slug>.md
```

Key design properties that make testing tractable:

- **The model is boxed in.** It receives a fixed evidence bundle and must return
  a schema-constrained object. Input and output are both typed and inspectable.
- **`inspect` exposes the whole deterministic half** — ranked files with a
  per-signal score breakdown and the exact snippets that would be sent — with no
  API call. This is the primary debugging/tuning surface.
- **The renderer is pure**: same plan in → byte-identical Markdown out.

---

## Reading the output (what each command shows you)

### `codegraft inspect "<request>" --repo <path>`

```
codegraft - implementation plans for coding agents

Repo: C:\...\codegraft
Discovery: git ls-files  Kept: 43  Skipped: 0  Mode: normal      ← (1)
Primary: Python   Frameworks: Pydantic                            ← (2)
Languages: Python=36
Manifests: pyproject.toml
Entry points: —
Ranking signal: add an openai provider (full request ...)        ← (3) only if request was long
┏━━━━┳━━━━━━━┳───────────────────────────┳─────────────────────┓
┃  # ┃ Score ┃ Path                      ┃ Signals             ┃ ← (4)
┃  1 ┃  17.3 ┃ src/codegraft/models/plan ┃ filename=+6.0 ...   ┃
Context bundle: 12 snippets, 32194 chars (budget 50000)          ← (5)
```

1. **Discovery line.** `Kept` = files that survived ignore+safety filtering and
   are eligible evidence. `Skipped` = excluded (add nothing); when non-zero a
   `Skips by reason:` line breaks it down (`secret`, `binary`, `oversized`,
   `generated`, `excluded`). `git ls-files` vs `filesystem walk` tells you which
   discovery path ran. `Mode` is `normal`/`medium`/`large` — `large` means
   ranking got conservative; consider `--subdir`.
2. **Summary block.** What kind of codebase this is — primary language, detected
   frameworks, root manifests, likely entry points.
3. **Ranking signal.** Appears only when the request was long enough to be
   focused (see §1). It shows the short phrase that actually drove file ranking;
   the full request still goes to the model.
4. **Ranked table.** `Score` is the total relevance score (higher = more
   relevant); it is exactly the sum of the `Signals`. Read the signals to
   understand *why* a file ranked where it did (glossary below).
5. **Context bundle.** How many snippets and characters would be sent to the
   model, against the configured budget. This is the evidence the plan is built
   from. Add `--snippets` to print the actual extracted slices (line-numbered;
   `...` marks skipped lines; a file tagged `truncated` hit the per-file line cap).

#### Signal glossary (the ranking "why")

Each signal is a named contribution to a file's score. Positive signals push a
file up; the diversity penalty is the only negative one.

| Signal | Meaning | Weight |
|--------|---------|--------|
| `filename` | a request keyword appears in the file's own name | +6.0 each |
| `path` | a request keyword appears elsewhere in the path | +3.0 each |
| `symbol` | a keyword matches a defined name (`def`/`class`/`func`…) in a **code** file | +4.0 each |
| `content` | request keywords occur in the file body | +0.4 each, capped at +4.8 |
| `role` | the path sits in an architectural folder (`routes`, `services`, `models`, `auth`, …) | +1.5 to +3.0 |
| `entry_point` | the file is a likely app entry point (`main.py`, `index.ts`, …) | +2.0 |
| `manifest` | a root/build manifest (`pyproject.toml`, `package.json`, …) | +1.5 |
| `test` | a test file, *and* the request looks test-related | +1.5 |
| `proximity` | a shallow (near-root) file | +1.0 |
| `diversity_penalty` | this file shares a folder with higher-ranked files (stops one dir dominating) | −1.5 each, capped at −4.5 |

Rule of thumb: a healthy top result usually combines a `filename`/`symbol` hit
with `content` and/or `role`. A top result carried only by `content` on a doc
file is a sign the request keywords are too generic — tighten the request.

### `codegraft plan "<request>" --repo <path>`  →  `plans/<date>-<slug>.md`

The Markdown plan always contains the same sections, in order. How to read each:

| Section | What it tells you / how to judge it |
|---------|-------------------------------------|
| Feature Summary | one-paragraph restatement of intent — sanity-check it matches what you asked |
| Assumptions / Open Questions | where the model was uncertain — surfaced, not buried |
| Relevant Architecture | the model's understanding of the codebase from the evidence |
| **Files Reviewed** | the anti-hallucination anchor — **every path here should actually exist in your repo**; if one doesn't, that's a red flag |
| **Files Likely To Modify** | the actionable handoff — the concrete change set |
| Data / API / UI Changes | scoped impact per layer (`None expected.` is a valid, deliberate answer) |
| Implementation Phases | bounded steps — each has Goal, Likely files, Tasks, Acceptance criteria, Validation. Good phases are small, ordered, independently shippable |
| Risks | each tagged `[high]`/`[medium]`/`[low]` with a mitigation |
| Test Plan | recommended unit/integration/e2e/regression tests |
| Claude Code Prompts | paste-ready, per-phase handoff prompts — should stand alone |
| Definition Of Done | concrete completion checklist |
| Generation Metadata | provenance — provider, model, repo root, timestamp, file counts (authored by codegraft, not the model) |

Use `--stdout` to print instead of writing a file, `--dry-run` to build without
writing, and `--stub` to produce an offline placeholder (every section marked
`[STUB]`) without an API key.

### `pytest` output

A line of dots is one char per test: `.` pass, `s` skipped, `F` fail, `E` error.
The trailing `s` in `62 passed, 1 skipped` is the opt-in live test
(`test_live_anthropic_smoke`), which self-skips unless `ANTHROPIC_API_KEY` is set
and you run `pytest -m live_anthropic`.

---

## 2. How output quality can be gated or measured

Quality splits cleanly along the deterministic / LLM boundary.

### 2a. Deterministic layer — objectively measurable

| What | Metric | How |
|------|--------|-----|
| Discovery correctness | exact set match | fixture repos: tracked+untracked, ignores respected, secrets/binaries excluded |
| **Ranking quality** | **recall@N** | for known `(request → expected files)` pairs, is each expected file in the top N? |
| Ranking sharpness | relevant > irrelevant | a clearly-relevant file must outscore a clearly-irrelevant one |
| Token discipline | bundle ≤ budget | `context_chars ≤ context_char_budget`; per-file ≤ line cap |
| Explainability | signals sum to score | every `RankedFile.score == sum(signals.values())` |

`recall@N` is the single most useful ranking metric: pick a handful of feature
requests for a fixture repo, list the files a human would expect to touch, and
check how many land in the top N. It turns "is the ranking good?" into a number.

### 2b. LLM layer — gateable even though the plan is subjective

The plan text is a judgment call, but several quality properties are
**machine-checkable** and make excellent gates:

1. **Schema parse (binary gate).** The response either validates into
   `ImplementationPlan` or it doesn't. A parse failure is an automatic fail.
2. **Anti-hallucination gate (the strong one).** Every path in
   `files_reviewed` must actually appear in the evidence bundle that was sent. If
   the model "reviewed" a file it was never given, that's a measurable
   hallucination. This can be asserted in code, not just eyeballed.
3. **Section completeness.** The renderer guarantees every section renders; a
   gate asserts required headings are always present (already tested).
4. **Grounded modifications.** Files in `files_likely_to_modify` should be either
   in the bundle or plausibly new paths consistent with the tree (softer check).
5. **Human rubric (final, manual).** For a demo request, a reviewer rates: are
   the phases bounded and ordered? Are acceptance criteria observable? Do the
   Claude Code prompts stand alone? Is anything obviously wrong about the repo?

> Gate #2 is worth promoting into code: a post-parse validator that flags any
> reviewed file not present in the bundle. It directly measures the property the
> whole "evidence-backed" pitch rests on. (Not yet implemented — candidate for a
> follow-up.)

### 2c. Cost/value

- **Tokens saved** (planned mini-feature): estimated tokens of sending the
  bounded bundle vs. the whole candidate set — quantifies the selective-context
  value in one number.

---

## 3. Testing plan with gates

Three layers, cheapest first. Each gate is phrased as **"working if X."**

### Layer 1 — Automated, deterministic (run on every change: `pytest`)

| Component | Working if… | Covered by |
|-----------|-------------|------------|
| Discovery (git) | tracked + untracked returned; a tracked file stays listed even after a matching `.gitignore` rule | `test_discovery.py` |
| Ignore fallback | nested `.gitignore` scoped to its subtree; `.git/` always skipped | `test_ignore.py` |
| Safety | `.env`, `*.pem`, binaries, oversized files are excluded with the right reason | `test_discovery.py`, `test_ignore.py` |
| Detection | language mix / manifests / entry points / tests identified | `test_detect.py` |
| Ranking | relevant files rank above irrelevant; content-only files still rank; doc code-blocks don't score as symbols; `score == Σ signals` | `test_rank.py` |
| Snippets | output ≤ per-file line cap and ≤ total char budget; header + keyword windows present | `test_snippets.py` |
| Request focusing | long request → heading/first-line/first-sentence; short request unchanged | `test_text.py` |
| Renderer | every required section always present; pipes in cells escaped; matches the checked-in sample byte-for-byte | `test_renderer.py` |
| CLI surface | `init`/`inspect`/`plan` exit cleanly; `--stub`/`--request-file`/`--dry-run`/`--stdout` behave | `test_cli.py` |

**Gate:** `pytest` is green → the deterministic engine is doing what it's supposed to.

### Layer 2 — Automated, mocked provider (no API key)

| Component | Working if… | Covered by |
|-----------|-------------|------------|
| Prompt assembly | system prompt + XML user message contain the request, tree, and snippets | `test_providers.py` |
| Anthropic adapter | calls `messages.parse(output_format=ImplementationPlan)`; sends `temperature` only to models that accept it; wraps SDK errors; raises on unparsable response | `test_providers.py` |
| Orchestration | metadata is stamped by codegraft (not the model); the provider receives the analyzed bundle | `test_providers.py` |
| Provider factory | unknown/openai providers raise a clear error | `test_providers.py` |

**Gate:** mocked provider tests green → the contract and wiring are correct
without spending a token.

### Layer 3 — Manual / live (run occasionally, needs a key for the last two)

| Check | Working if… | How |
|-------|-------------|-----|
| Ranking eyeball | top files match intuition on a real project | `codegraft inspect "<request>" --repo <some-real-repo>` |
| Long-request focus | the surfaced "Ranking signal" is the goal sentence; bundle stays small | `codegraft inspect --request-file <file> --repo .` |
| Live plan (smoke) | a real plan parses into the schema and has phases | `pytest -m live_anthropic` (needs `ANTHROPIC_API_KEY`) |
| Live plan (quality) | `files_reviewed` are all real; sections all present; phases bounded & ordered; prompts stand alone | run `codegraft plan` on a demo repo, read `plans/<…>.md` against the rubric in §2b |

**Gate:** for a real plan against `examples/` or a small backend repo —
"this is doing what it's supposed to do if" the output parses, every reviewed
file actually exists in the repo, every section is present, and a human agrees
the phases are sensible and executable.

---

## Quick reference — the four gates that matter most

1. `pytest` is green. *(deterministic engine correct)*
2. Mocked provider tests green. *(contract + wiring correct)*
3. `inspect` on a few real repos produces sensible top-N rankings. *(ranking quality)*
4. One live plan parses, has no hallucinated reviewed files, renders all sections,
   and reads as a plan an engineer would actually follow. *(end-to-end quality)*
