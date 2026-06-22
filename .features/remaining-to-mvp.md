# Remaining to MVP

Tracking what's left from the blueprint to reach **Polished Portfolio V1**.
Source of truth for scope: `project-report-and-blueprint.md` + `CLAUDE.md`
guardrails. Update checkboxes as work lands.

Legend: ✅ done · 🟡 doing · ⬜ todo

---

## Build phases

### Phase 1 — Foundation & contract ✅
- [x] Package skeleton (`src/codegraft`, `pyproject.toml`)
- [x] Typed config (`config.py`): `codegraft.toml` + `.env` secrets; model id is config
- [x] Typed `ImplementationPlan` schema + sub-models (`models/plan.py`)
- [x] Typer CLI: `init`, `inspect` (placeholder), `plan` (`cli.py`)
- [x] Deterministic Markdown renderer, always emits every section (`renderer.py`)
- [x] Stub end-to-end plan path writing to `/plans` (`service.py`)
- [x] `CLAUDE.md` with commands, architecture, scope guardrails
- [x] CLI + renderer + filename tests (14 passing)
- [x] Windows UTF-8 console fix

### Phase 2 — Discovery & ignore engine ✅
- [x] Git-aware discovery: `git ls-files --cached` + `--others --exclude-standard`,
      `--full-name -z` (two scoped calls to label tracked vs untracked)
- [x] Filesystem fallback via PathSpec `GitIgnoreSpec` with nested `.gitignore` scoping
- [x] Safety denylist owns secrets/binaries: `.env*`, `*.pem/key/crt/...`, private
      keys, certs, `.npmrc`/`.pypirc`, minified/generated, NUL-byte binary sniff,
      oversized (`max_file_bytes`)
- [x] `max_candidate_files` cap with `truncated` flag (line cap deferred to Phase 3
      snippet reading, where files are read anyway)
- [x] Typed file-metadata models (`models/repo.py`: `RepoFile`, `SkippedFile`, `RepoScan`)
- [x] Real `inspect`: discovery summary, skip-by-reason counts, candidate table
- [x] Tests: tracked+untracked, tracked-but-later-ignored survives, untracked+ignored
      excluded, secrets/binaries/oversized excluded, nested gitignore, dir pruning,
      fallback path (`tests/test_discovery.py`, `test_ignore.py`) — 27 passing total
- [x] Modules: `repo/discover.py`, `git_scan.py`, `ignore.py`, `safety.py`
- Note: `extra_excludes` now covers only vendor/build dirs; `safety.py` is the
  single authority for secrets (keeps skip reasons accurate).

### Phase 3 — Repo summary, ranking, snippets ✅
- [x] Compact depth-limited directory tree (`repo/tree.py`)
- [x] Language/framework/manifest/entry-point detection (`repo/detect.py`)
- [x] Repo summary assembly + scale-mode (`repo/summarize.py`)
- [x] Deterministic **two-stage** relevant-file ranking (`repo/rank.py`):
      cheap path/role/structure pass over all files → content+symbol pass on top
      candidates → diversity penalty (capped). Explainable `signals` per file.
- [x] Reusable keyword/identifier tokenizer (`utils/text.py`)
- [x] Bounded snippet extraction under char + per-file-line budget (`repo/snippets.py`)
- [x] **Real `inspect` command**: summary panel + scored ranked table + snippet
      stats; `--subdir`, `--snippets` flags
- [x] Single analysis entry point (`repo/analyze.py` → `RepoAnalysis`) reused by Phase 4
- [x] Large-repo graceful degradation (normal/medium/large mode, warn + `--subdir`)
- [x] Tests: ranking sanity, content-only + doc-codeblock regressions, snippet
      budget, detection/tree (`tests/test_rank.py`, `test_snippets.py`, `test_detect.py`)
      — 43 passing total
- Ranking tuned against codegraft's own `inspect` output; fixed two real bugs the
  surface exposed (symbol-scoring on doc code blocks; content-only files dropped
  before content read). See `cautions-and-pushbacks.md` #1.

### Phase 4 — Anthropic planning core ✅
- [x] **Verified Anthropic structured-output API** (caution #3 resolved): real
      support via `messages.parse(output_format=<Pydantic>)` → `.parsed_output`;
      no JSON-mode fallback needed
- [x] `PlanProvider` protocol + `PlanningRequest` bundle (`providers/base.py`)
- [x] Anthropic provider with lazy/injectable SDK client (`providers/anthropic_provider.py`)
- [x] System prompt as package resource (`prompts/planner_system.md`) + XML user
      message assembly (`providers/prompt.py`)
- [x] Structured output → validated `ImplementationPlan`; ProviderError /
      PlanValidationError on failure (fails loudly)
- [x] Real `generate_plan` orchestration replacing the stub; metadata stamped by
      codegraft, not the model (`planning/service.py`); `plan --stub` kept offline
- [x] Provider factory `get_provider`; cross-model temperature gating
      (omits sampling params for Opus 4.7+/Fable)
- [x] Mocked provider/prompt/service tests + opt-in `live_anthropic` marker
      (`tests/test_providers.py`) — 54 passing, 1 opt-in skipped
- Note: `max_output_tokens` raised 5000→8000 to avoid truncating a full plan.

### Phase 5 — Markdown rendering & request handling ✅
- [x] Renderer polish: table-cell escaping (pipes/newlines can't break tables)
- [x] Per-phase Claude Code prompts rendered from phase data (done since Phase 1)
- [x] Timestamped filenames into `/plans` (done since Phase 1)
- [x] Snapshot renderer test against a checked-in example (deterministic metadata)
- [x] Checked-in `examples/sample_plans/add-rbac.md` + `examples/demo_requests/add-rbac.md`
- [x] **Title/body ranking-signal split** (`utils/text.ranking_signal`): long
      requests are ranked by their heading/first-line/first-sentence while the
      full text goes to the model — keeps ranking sharp on verbose requests
- [x] **`inspect --request-file`** + surfaces the ranking signal when it differs
- [x] `RepoAnalysis.ranking_signal` exposed; tests for signal + snapshot + cell-escape
      (`tests/test_text.py`, `test_renderer.py`) — 62 passing, 1 opt-in skipped

### Mini-feature — Estimated token savings ✅
Quantify the selective-context thesis: how many tokens codegraft *avoided*
sending by shipping a bounded bundle instead of the whole candidate set.
- [x] `utils/tokens.py`: `estimate_tokens(chars)` (~4 chars/token heuristic,
      labelled an estimate — NOT tiktoken; `TokenEstimate` + `estimate_savings`)
- [x] `RepoAnalysis.token_estimate()`: baseline = Σ `size_bytes` of the
      **selected** files (the snippet sources, read in full — the realistic
      alternative an agent would open, *not* the whole repo) vs bundle =
      `context_chars`; reports `saved_tokens` + `saved_pct`, clamped ≥ 0
- [x] Surfaced in `inspect` (one line) and in the plan's Generation Metadata
      (two new fields on `GenerationMetadata`, stamped by the service; renderer
      prints them; snapshot regenerated). `--json` exposure lands with Phase 6.
- [x] Tests (`tests/test_tokens.py`) — estimator, savings math, clamping, empty
      repo, end-to-end on a fixture. 67 passing, 1 opt-in skipped.
- Live check: "add an openai provider" on this repo → ~11k sent vs ~34k to read
  the 12 selected files in full → ~23k (68%) saved. (Earlier this read ~46k/83%
  against the *whole repo* — an inflated baseline; corrected to the realistic
  "read the surfaced files" comparison.)

### Phase 6 — OpenAI provider & portfolio polish ✅
- [x] OpenAI provider behind same `PlanProvider` contract (`providers/openai_provider.py`),
      reusing the identical prompt assembly; mocked tests mirroring Anthropic
- [x] Raw plan JSON debug artifact: `plans/_debug/<stem>.plan.json` (when
      `output.write_debug_json`)
- [x] `--json` output option for `plan` (scripting)
- [x] Demo request + sample output (`examples/demo_requests/`, `sample_plans/`) *(Phase 5)*
- [x] README polish: pitch, why, quickstart, real example capture, architecture
      notes, limitations, roadmap
- [x] `docs/architecture.md` (data flow, design decisions, deterministic/LLM boundary)
- [~] Captures: real terminal output embedded in README; image screenshots under
      `docs/screenshots/` left as an optional nicety
- Deferred (V2, low value now): `--debug-context` dump of the assembled prompt;
      Anthropic `count_tokens` for exact token counts.

---

## Scope tiers (blueprint)

**Should-have** (fold into phases above)
- [ ] `--stdout` / `--json` output options  *(`--stdout` done; `--json` pending Phase 6)*
- [ ] Debug artifact of selected files + context snippets  *(Phase 6)*
- [x] Richer Rich formatting for ranking previews / summaries / status
- [x] `--request-file` for both `plan` and `inspect`; long-request title/body split

**Nice-to-have** (only if genuinely easy)
- [ ] Shell completion via Typer
- [ ] Token-estimate command / debug readout
- [ ] Prompt caching for repeated runs in same repo
- [ ] Narrow Python-only AST summarizer for top-level defs
- [ ] Repo-analysis cache keyed by file hashes

**V2 — started**
- [x] **MCP server** (`src/codegraft/mcp.py`, `[mcp]` extra, `codegraft-mcp` script):
      exposes the engine as agent tools — `select_context` (deterministic, free,
      the differentiated piece) + `generate_plan` (opt-in LLM). Thin adapter over
      `analyze_repo`; mocked-free payload tests. The strategic pivot: expose the
      deterministic context engine to coding agents, not the commodity LLM planner.
      See `experiment-meshimate-ab.md` for the reasoning that motivated it.
- [ ] Import-graph ranking boost (pull in a file imported by several top-ranked
      files — the gap the MeshiMate run exposed). Open.

**Explicitly deferred to V2** (do NOT build — see `CLAUDE.md`)
- Full AST / tree-sitter across languages · embeddings / vector stores / RAG ·
  git-diff validation vs plan · multi-agent planner+reviewer · SQLite project
  memory · remote repo cloning · IDE plugins / MCP / web UI · hosted backend /
  accounts / teams / sync · direct code editing or running the agent for you.

---

## V1 Definition of Done (gate before calling it shipped)
- [x] `codegraft plan` works on a fixture repo (mocked) + offline `--stub`;
      live Anthropic path is opt-in (`-m live_anthropic`) — **user to run with
      their own key**
- [x] Scanner respects Git-aware ignore; excludes secret/binary/noise files
- [x] Compact repo summary + ranked relevant files produced
- [x] Context bundle stays under configured limits
- [x] Anthropic provider works end to end (mocked + opt-in live)
- [x] Plan parsed into typed schema before rendering
- [x] Markdown lands in `/plans` with all required sections every time
- [x] Claude Code prompts rendered phase by phase
- [x] ≥1 believable demo request + ≥1 checked-in sample plan
- [x] `codegraft inspect` exists and is useful (the ranking/tuning surface)
- [x] Core repo-analysis, renderer snapshot, and CLI tests pass (73 + 1 opt-in)
- [x] README explains install, usage, architecture, limitations
- [~] Terminal captures embedded in README; image screenshots optional
- [x] Tradeoffs explainable in an interview without hand-waving
- ⏳ One live `plan` run + human read of the output (needs the user's API key)

---

## Effort markers (blueprint estimate)
Barebones MVP ≈ 8–12h · Polished V1 ≈ 16–24h. Build order is **golden-path
first**: a complete vertical slice early (Phase 1 ✅), then deepen discovery and
quality. First scope cut under time pressure: ship Anthropic-first, defer the
OpenAI shipping provider (keep the abstraction).
