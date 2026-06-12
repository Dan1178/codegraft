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

### Phase 3 — Repo summary, ranking, snippets ⬜  *(next)*
- [ ] Compact depth-limited directory tree (`repo/tree.py`)
- [ ] Language/framework/manifest/entry-point detection (`repo/detect.py`)
- [ ] Repo summary assembly (`repo/summarize.py`)
- [ ] Deterministic relevant-file ranking (`repo/rank.py`):
      path/keyword/symbol overlap + role boosts + manifest/entry proximity +
      test-convention boost − noise/oversize penalty + diversity penalty
- [ ] Bounded snippet extraction under budget (`repo/snippets.py`)
- [ ] **Real `inspect` command**: print ranked files + scores (no model call)
- [ ] Large-repo graceful degradation (<500 normal / 500–2500 medium / >2500 warn + `--subdir`)
- [ ] Tests: ranking sanity on fixtures, snippet budget enforcement
      (`tests/test_rank.py`, `test_snippets.py`)

### Phase 4 — Anthropic planning core ⬜
- [ ] **Verify Anthropic structured-output API for real** (see cautions #3)
- [ ] `PlanProvider` protocol (`providers/base.py`)
- [ ] Anthropic provider (`providers/anthropic_provider.py`)
- [ ] XML-tagged prompt templates (`prompts/planner_system.md`, `planner_user.md`, `phase_prompt.md`)
- [ ] Prompt assembly from deterministic context blocks
- [ ] Structured output → validated `ImplementationPlan`; fail loudly on malformed
- [ ] Planning orchestration replaces the stub (`planning/service.py`)
- [ ] Mocked provider tests + opt-in `live_anthropic` marker (`tests/test_providers.py`)

### Phase 5 — Markdown rendering & handoff prompts ⬜
- [ ] Renderer polish; confirm all required sections stable from real plans
- [ ] Per-phase Claude Code prompts rendered from phase data (not a 2nd LLM call)
- [ ] Timestamped filenames into `/plans`
- [ ] Snapshot-style renderer tests (`tests/test_renderer.py` expansion)
- [ ] Checked-in `examples/sample_plans/`

### Phase 6 — OpenAI provider & portfolio polish ⬜
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
- [ ] Debug artifact of selected files + context snippets
- [ ] Richer Rich formatting for ranking previews / summaries / status

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
