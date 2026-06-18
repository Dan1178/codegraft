# codegraft architecture

codegraft is a pipeline with a single LLM call in the middle. Everything before
and after that call is deterministic and unit-tested, which is the property that
makes the system explainable and cheap to verify.

## Data flow

```
repo path + feature request
        │
        ▼
  CLI (cli.py)  ──  config resolution (config.py)
        │              codegraft.toml (behaviour) + .env (secrets, never logged)
        ▼
  ┌─────────────────────────── DETERMINISTIC ───────────────────────────┐
  │  repo/analyze.py orchestrates:                                        │
  │                                                                       │
  │  discover (discover.py)                                               │
  │    ├─ git_scan.py   git ls-files: tracked + untracked, labelled       │
  │    ├─ ignore.py     filesystem fallback, nested .gitignore (PathSpec) │
  │    └─ safety.py     deny secrets / keys / binaries / oversized / noise │
  │  summarize (summarize.py)                                             │
  │    ├─ tree.py       compact depth-limited directory tree              │
  │    └─ detect.py     language / framework / manifest / entry / tests   │
  │  rank (rank.py)     two-stage explainable score per file              │
  │    └─ utils/text.ranking_signal()  focuses long requests             │
  │  snippets (snippets.py)  header + keyword windows, under budget       │
  │  utils/tokens.py    estimated tokens saved vs. dumping the repo       │
  └───────────────────────────────────────────────────────────────────────┘
        │
        ▼  PlanningRequest (providers/base.py) — the evidence bundle
        │
        ▼  ┌──────────────── THE ONE LLM CALL ────────────────┐
           │  providers/prompt.py   system prompt + XML user   │
           │  anthropic_provider.py / openai_provider.py       │
           │  structured output → validated ImplementationPlan │
           └────────────────────────────────────────────────────┘
        │
        ▼  planning/service.py  stamps provenance metadata (not the model)
        ▼  planning/renderer.py  stable Markdown, every section always present
        │
        ▼  plans/<date>-<slug>.md   (+ optional plans/_debug/<stem>.plan.json)
```

## Key design decisions

### 1. A typed output contract (`models/plan.py`)
The model returns a validated `ImplementationPlan` (Pydantic), not Markdown. This
gives reliable parsing, deterministic rendering, snapshot tests, and `--json`
for free. How that JSON is obtained differs by provider:

- **Anthropic** uses *instructed JSON* — the schema is embedded in the prompt and
  the response is validated with Pydantic. It does **not** use grammar-constrained
  structured outputs (`messages.parse`): the engine compiles the schema into a
  decoding grammar up front, which times out on a schema this large ("Grammar
  compilation timed out"). Instructed-JSON keeps the typed contract without that
  dependency.
- **OpenAI** uses `chat.completions.parse(response_format=ImplementationPlan)`,
  whose structured-output engine handles the schema without that limitation.

Either way the boundary is the same: a validated Pydantic object in, Markdown out.

### 2. Deterministic context assembly
Selecting *which files the model sees* is the core engineering problem, and it's
done without the model: a deterministic ranker scores every candidate file and a
budgeted extractor pulls bounded snippets. `inspect` exposes the whole thing —
ranked files with a per-signal breakdown — so ranking is debuggable, not magic.

### 2a. One engine, three interfaces (ports & adapters)
`repo/analyze.py` (`analyze_repo → RepoAnalysis`) is the deterministic core.
Three thin adapters consume it, none owning logic the others need:
`cli.py` (human interface), `mcp.py` (agent interface — an MCP server exposing
the free/deterministic read-side tools `select_context` / `impact_of` /
`get_symbol` / `affected_tests` plus the opt-in `generate_plan`), and
`providers/*` (the LLM interface). Adding the MCP server was ~one module over
the existing core — the payoff of isolating the engine.

### 2b. Read-side query tools (`repo/imports.py`, `graph.py`, `symbols.py`)
A second family of consumers reuses the analysis layer's machinery but bypasses
the provider entirely — deterministic, model-free queries pointed at the same
"what should I look at?" mission. The import resolver that powers ranking's
`imported_by` signal was extracted from `rank.py` into `repo/imports.py`
(`build_import_graph` → forward/reverse edges); `rank.py` re-imports it unchanged,
so the ranking heuristic is byte-for-byte the same. On top of that graph:
`impact_of` (reverse dependencies — blast-radius triage), `affected_tests`
(reverse closure ∩ the repo's test files — *selection only, never execution*), and
`get_symbol` (`repo/symbols.py` — the bounded snippet extractor at symbol
granularity). All three are heuristic and stamp `resolution`/`completeness:
"heuristic"`; each surfaces through both `cli.py` and `mcp.py`, and each has a
git-history validator (`evaluation_graph.py`, `evaluation_symbol.py`) that
baselines its value the way `evaluation.py` grades ranking.

### 3. Provider abstraction (`providers/`)
`PlanProvider` is a one-method protocol: `generate_plan(PlanningRequest) ->
ImplementationPlan`. The prompt assembly (`providers/prompt.py`) is shared, so
adding OpenAI was a new adapter plus factory wiring — the prompt and schema were
untouched. SDKs are optional deps, imported lazily; clients are injectable so the
test suite never needs a key or a network.

### 4. The privacy boundary
The raw repository never leaves the machine. Discovery and ranking run locally;
only the small selected snippet bundle is sent to the provider. The safety
denylist (`repo/safety.py`) is the authority for what must never enter that
bundle (secrets, keys, certs, binaries).

### 5. Trustworthy provenance
Generation metadata — provider, model, timestamp, file counts, token estimate —
is stamped by `planning/service.py` after parsing, never authored by the model.
So the metadata reflects what codegraft actually did, regardless of model output.

## Where the LLM is, and isn't

| Stage | Deterministic? |
|-------|----------------|
| Discovery, ignore, safety | ✅ |
| Summary, language/framework detection | ✅ |
| Relevant-file ranking | ✅ (heuristic, no model) |
| Snippet extraction + budgeting | ✅ |
| Token-savings estimate | ✅ |
| **Plan generation** | ❌ — the single model call |
| Plan → Markdown rendering | ✅ |
| Metadata stamping | ✅ |

This boundary is the reason `inspect` can show you almost the entire system with
no API call, and why the test suite (70+ tests) covers behaviour without mocking
much beyond the one provider call.
