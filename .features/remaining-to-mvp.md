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

### Phase 6 — OpenAI provider & portfolio polish ⬜  *(next)*
- [ ] OpenAI provider behind same `PlanProvider` contract (`providers/openai_provider.py`)
- [ ] Debug artifacts: selected files + raw plan JSON (`plans/_debug/`)
- [ ] `--json` / `--debug-context` output options
- [ ] Demo request + sample output (`examples/demo_requests/`, `sample_plans/`)
- [ ] README polish: install, quickstart, architecture, limitations, roadmap
- [ ] Screenshots: `inspect` output, `plan` run, generated-plan excerpt (`docs/screenshots/`)
- [ ] `docs/architecture.md`

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

**Explicitly deferred to V2** (do NOT build — see `CLAUDE.md`)
- Full AST / tree-sitter across languages · embeddings / vector stores / RAG ·
  git-diff validation vs plan · multi-agent planner+reviewer · SQLite project
  memory · remote repo cloning · IDE plugins / MCP / web UI · hosted backend /
  accounts / teams / sync · direct code editing or running the agent for you.

---

## V1 Definition of Done (gate before calling it shipped)
- [ ] `codegraft plan` works on ≥1 real repo and ≥1 fixture repo
- [ ] Scanner respects Git-aware ignore; excludes secret/binary/noise files
- [ ] Compact repo summary + ranked relevant files produced
- [ ] Context bundle stays under configured limits
- [ ] Anthropic provider works end to end
- [ ] Plan parsed into typed schema before rendering
- [ ] Markdown lands in `/plans` with all required sections every time
- [ ] Claude Code prompts rendered phase by phase
- [ ] ≥1 believable demo request + ≥1 checked-in sample plan
- [ ] `codegraft inspect` exists and is useful
- [ ] Core repo-analysis, renderer snapshot, and CLI tests pass
- [ ] README explains install, usage, architecture, limitations
- [ ] Screenshots / terminal captures exist
- [ ] Tradeoffs explainable in an interview without hand-waving

---

## Effort markers (blueprint estimate)
Barebones MVP ≈ 8–12h · Polished V1 ≈ 16–24h. Build order is **golden-path
first**: a complete vertical slice early (Phase 1 ✅), then deepen discovery and
quality. First scope cut under time pressure: ship Anthropic-first, defer the
OpenAI shipping provider (keep the abstraction).
