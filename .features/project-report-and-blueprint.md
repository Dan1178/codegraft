# CodeGraft implementation plan

## Strategic recommendation

### Executive Recommendation

codegraft is worth building now, but only if you build the narrow, high-signal version of it: a **local-first brownfield implementation-planning CLI** for existing repositories. That is a real gap in the current tooling landscape. Repo-packers such as **Gitingest** and **Repomix** are optimized for turning repositories into prompt-friendly digests, not for turning a *feature request plus repository evidence* into a structured engineering plan. Context-heavy coding tools such as **Aider** and **Sourcegraph Cody** invest heavily in repository maps, search, and codebase context. **GitHub Spec Kit** is centered on more formal spec-driven workflows, while **Plandex** pushes toward large-task planning, execution, sandboxed diffs, and tree-sitter-backed large-project handling. The best wedge for you is therefore not “another full coding agent,” but “the tool that creates a practical, evidence-backed implementation plan for coding agents from a real local codebase.” citeturn8view8turn8view7turn8view9turn9view0turn18view0turn18view1turn18view2turn18view4

This also lines up well with how **Claude Code** itself is documented to work best: explore first, then plan, then code; provide specific context; and give the agent a way to verify its work. A tool that improves planning artifacts and handoff quality for Claude Code is not a gimmick; it is directly aligned with the workflow the downstream agent expects. citeturn19view0turn20view0turn20view1

My judgment is that **Polished V1 is feasible over a focused weekend**, but it is **not** feasible if you let it slide toward embeddings, tree-sitter project maps, git-diff validation, multi-agent orchestration, or collaboration features. Mature tools in this area already show that those bigger features quickly become their own projects: Aider talks explicitly about repository maps, Plandex talks about tree-sitter project maps and very large-context workflows, and Sourcegraph Cody relies on a search-driven context engine. So the correct move is a strict V1 split: **weekend core** first, **polish pass** second. citeturn8view9turn18view4turn9view0turn10view0

Relative to your recipe app, I would treat codegraft as roughly **twice as hard** in the part that matters: not because it needs more screens or CRUD, but because the hard work shifts to **context engineering, output reliability, ranking quality, and plan usefulness**. If you stay disciplined, it is still a fast project; if you chase “AI platform” energy, it becomes a multi-week sink. That estimate is my judgment based on the scoped architecture below.

### Product Definition

**codegraft** should be defined as a **local-first implementation-planning CLI** that takes:

- a local repository
- a feature request
- optional config and provider settings

and produces:

- a structured Markdown implementation plan
- impacted-file analysis
- risks and test recommendations
- phase-by-phase execution prompts for Claude Code or similar coding agents

The core problem it solves is that coding agents work much better when they are handed **the right context, a bounded plan, and explicit verification criteria**. Claude Code’s own docs emphasize codebase exploration, planning before editing, narrow context, and explicit checks that the agent can run. codegraft exists to manufacture those planning artifacts automatically and consistently. citeturn19view0turn19view1turn20view0

The intended user for V1 is **you first**: a solo engineer using coding agents across multiple personal repositories. That means the product should optimize for **clarity, explainability, architecture quality, and visible tradeoff decisions**, not just “it generated something once.”

What makes codegraft more than a thin LLM wrapper is the **deterministic pipeline around the model**:

- repository discovery that respects ignore rules
- safe filtering and context budgeting
- language- and architecture-aware summaries
- relevant-file ranking
- selective snippet extraction
- schema-constrained plan generation
- deterministic Markdown rendering
- explicit handoff prompts

That shape matters. GitHub’s Spec Kit explicitly frames spec-driven work as **multi-step refinement rather than one-shot prompting**, and Claude Code likewise recommends an explore-plan-code pattern rather than raw prompt dumping. codegraft should inherit that discipline, even in a much smaller, faster-to-build form. citeturn18view1turn19view0

### V1 Scope

The cleanest V1 boundary is:

**Must-have**

- A Python CLI with a real `plan` command and a small but complete command surface.
- Local repository analysis with **Git-aware scanning first** and sensible fallback behavior.
- Safe ignore logic that respects `.gitignore` and excludes obvious secrets, binaries, generated assets, and very large files.
- Compact codebase structure analysis: manifests, directory tree, language mix, likely architectural entry points.
- Relevant-file ranking for a feature request.
- Context extraction from top-ranked files under a hard budget.
- A typed internal `ImplementationPlan` schema.
- An **Anthropic provider implementation** and a provider abstraction layer.
- Deterministic Markdown rendering into `/plans`.
- Plan sections for risks, test strategy, phased implementation, and Claude Code prompts.
- A sample demo repository or at least a polished sample run with a checked-in example plan.
- A README that explains the problem, shows the workflow, and includes screenshots or terminal captures.

**Should-have**

- An `inspect` command that shows what codegraft thinks is important before calling the model.
- An **OpenAI provider implementation** using the same typed plan schema.
- A debug artifact showing selected files and context snippets used to generate the plan.
- `--stdout` and `--json` output options for scripting and debugging.
- Better Rich formatting for ranking previews, summaries, and completion status.

**Nice-to-have**

- Shell completion through Typer.
- A token-estimate command or debug readout.
- Optional prompt caching for repeated runs in the same repo.
- A very narrow Python-only AST summarizer for top-level defs, if it turns out to be genuinely easy.
- A repository-analysis cache keyed by file hashes.

**Explicitly deferred**

- Full AST or tree-sitter parsing across languages.
- Embeddings, vector stores, RAG infrastructure, or semantic indexing.
- Git diff validation of completed work against the plan.
- Multi-agent planning or reviewer orchestration by default.
- SQLite project memory.
- Remote repository cloning.
- IDE plugins, MCP servers, or a web UI.
- Hosted backend, accounts, team workspaces, or history sync.
- Direct code editing or “run Claude Code for me” execution flows.

Both Anthropic and OpenAI now support schema-constrained structured outputs, which means a typed internal plan object belongs in V1 rather than later. That one choice gives you better reliability, cleaner tests, and a cleaner architecture. citeturn8view5turn9view4

If schedule pressure hits, the first scope cut I would make is **OpenAI as a shipping provider**, not the abstraction. Keep the abstraction, ship Anthropic-first, and add OpenAI after the core flow is already solid.

## Proposed architecture

### Architecture

#### Recommended stack

Python is the right fit here. **Typer** is designed for type-hint-driven CLIs, automatic help, shell completion, and growth into larger command trees. **Rich** gives you strong terminal UX without building a UI. **Pydantic Settings** gives you typed config from environment variables and `.env` files. Both **Anthropic** and **OpenAI** provide official Python SDKs, and both expose structured output paths that fit a typed-plan architecture. citeturn12view0turn12view1turn12view2turn8view2turn8view3turn8view4turn8view5turn9view4

I recommend this V1 stack:

- Python 3.11+
- Typer
- Rich
- Pydantic
- Pydantic Settings
- PathSpec
- Anthropic SDK
- OpenAI SDK
- pytest

I would keep config local and simple. Use `.env` for keys and a repo-local config file for behavior. My recommendation is **`codegraft.toml`** for V1 because it is easy to parse and avoids extra YAML complexity, but YAML is fine if you care more about familiarity than dependency count. That format choice is not the value of the project; the pipeline is.

#### Folder structure

```text
codegraft/
  pyproject.toml
  README.md
  CLAUDE.md
  src/codegraft/
    __init__.py
    cli.py
    branding.py
    config.py
    errors.py

    models/
      plan.py
      repo.py
      provider.py

    repo/
      discover.py
      git_scan.py
      ignore.py
      detect.py
      tree.py
      summarize.py
      rank.py
      snippets.py
      safety.py

    prompts/
      planner_system.md
      planner_user.md
      phase_prompt.md

    providers/
      base.py
      anthropic_provider.py
      openai_provider.py

    planning/
      service.py
      renderer.py
      filenames.py

    utils/
      text.py
      tokens.py
      hashing.py
      io.py

  tests/
    fixtures/
      fastapi_demo/
      express_demo/
      ignore_cases/
    test_cli.py
    test_discovery.py
    test_ignore.py
    test_rank.py
    test_snippets.py
    test_renderer.py
    test_providers.py

  examples/
    demo_requests/
    sample_plans/

  docs/
    architecture.md
    screenshots/
```

That structure makes the boundaries obvious: **repo analysis**, **provider adapters**, **planning service**, and **rendering** are distinct concerns.

#### Core data flow

```text
repo path + feature request
        ↓
CLI + config resolution
        ↓
repository discovery
        ↓
ignore / safety / size filtering
        ↓
repo summary + manifests + tree
        ↓
relevant-file ranking
        ↓
snippet extraction under budget
        ↓
PlanningRequest
        ↓
provider adapter
        ↓
ImplementationPlan schema
        ↓
Markdown renderer + phase prompt renderer
        ↓
plans/<timestamp>-<slug>.md
```

That flow should stay mostly deterministic until the actual planning call. That is one of the strongest architecture decisions in the design.

#### Main modules

`repo.discover` should answer “what files exist that we are even willing to consider.”

`repo.ignore` and `repo.safety` should answer “what must never enter the context bundle.”

`repo.tree`, `repo.detect`, and `repo.summarize` should answer “what kind of codebase is this.”

`repo.rank` should answer “what files probably matter for this request.”

`repo.snippets` should answer “what exact evidence should be sent to the model.”

`providers.*` should only know how to turn a typed planning request into a typed planning response.

`planning.service` should orchestrate the whole run.

`planning.renderer` should turn a typed plan into stable Markdown and stable Claude Code prompts.

#### CLI commands

For V1, keep the CLI small and sharp:

- `codegraft init`  
  Creates `codegraft.toml` and prints env key requirements.

- `codegraft inspect`  
  Shows repo summary, top manifests, top directories, detected primary language stack, and ranked files for a request without invoking the model.

- `codegraft plan "..."`  
  Runs the full pipeline and writes a Markdown plan to `/plans`.

Useful flags:

- `--repo PATH`
- `--provider anthropic|openai`
- `--model MODEL_ID`
- `--request-file feature.md`
- `--max-files N`
- `--subdir PATH`
- `--stdout`
- `--json`
- `--dry-run`
- `--debug-context`

The `inspect` command is not fluff. It does double duty as a debugging surface for ranking quality and as a strong demo feature.

#### Config structure

A good V1 config shape is:

```toml
[provider]
name = "anthropic"
model = "CURRENT_BALANCED_MODEL"
temperature = 0.2
max_output_tokens = 5000

[repo]
respect_gitignore = true
prefer_git_ls_files = true
max_file_bytes = 180000
max_file_lines = 4000
max_candidate_files = 2500
extra_excludes = [
  "**/.env*",
  "**/*.pem",
  "**/*.key",
  "**/node_modules/**",
  "**/.venv/**",
  "**/dist/**",
  "**/build/**"
]

[analysis]
max_ranked_files = 12
max_snippet_lines_per_file = 160
always_include_manifests = true
include_tests_when_relevant = true
context_char_budget = 50000

[output]
output_dir = "plans"
write_debug_json = true
write_debug_context = false
```

Use `.env` for `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. Pydantic Settings supports typed settings from environment variables and dotenv files, which makes this a good fit for V1 without inventing custom secrets handling. citeturn8view2turn12view2

#### Provider abstraction

Do not make the model call return Markdown. Make it return a validated plan object.

A good interface is:

```python
class PlanProvider(Protocol):
    def generate_plan(self, request: PlanningRequest) -> ImplementationPlan:
        ...
```

A good typed domain model is:

```python
class ImplementationPlan(BaseModel):
    title: str
    feature_summary: str
    assumptions: list[str]
    open_questions: list[str]
    relevant_architecture: str
    files_reviewed: list[ReviewedFile]
    files_likely_to_modify: list[PlannedFileChange]
    data_model_changes: list[str]
    api_service_changes: list[str]
    ui_changes: list[str]
    implementation_phases: list[PlanPhase]
    risks: list[RiskItem]
    test_plan: list[TestItem]
    claude_code_prompts: list[AgentPrompt]
    definition_of_done: list[str]
```

This is one of the best V1 decisions you can make because both Anthropic and OpenAI now support structured outputs that constrain responses to a schema. Anthropic documents structured outputs as validated, parseable JSON for downstream workflows, and OpenAI documents Structured Outputs as JSON Schema-constrained outputs that reduce invalid or missing fields. citeturn8view5turn9view4

Also: **do not hardcode a model ID into your source code.** Anthropic’s docs explicitly distinguish active, legacy, deprecated, and retired models, and OpenAI’s model docs also change over time. Expose the model as config from day one. citeturn24search2turn26search0turn26search16

#### Prompt and template strategy

Use prompt templates stored as package resources and assemble them from deterministic context blocks. Anthropic explicitly recommends XML tags when prompts mix instructions, context, examples, and variable inputs, and that guidance applies very naturally here. citeturn9view3

The assembled planning prompt should have this shape:

```xml
<role>
You are an implementation planning assistant for existing software repositories.
</role>

<feature_request>
...
</feature_request>

<repo_summary>
...
</repo_summary>

<directory_tree>
...
</directory_tree>

<ranked_files>
...
</ranked_files>

<file_snippets>
  <file path="...">
    ...
  </file>
</file_snippets>

<constraints>
- Only assert file impact when there is evidence from the reviewed files.
- Put uncertainty in assumptions or open questions.
- Prefer phased implementation with clear validation steps.
</constraints>

<output_contract>
Return data matching the ImplementationPlan schema.
</output_contract>
```

Do **not** use a few-shot-heavy prompt in V1 unless you discover a real quality problem. Structured output plus a strong rubric is enough to ship a strong first version.

#### Output file structure

Write plans to the analyzed repository root:

```text
/plans/
  2026-06-11-add-org-rbac.md
  _debug/
    2026-06-11-add-org-rbac.plan.json
    2026-06-11-add-org-rbac.context.md
```

The Markdown file is the product. The JSON and context artifacts are there for debugging and transparency.

### Markdown Plan Format

The generated Markdown should be **stable**, **predictable**, and **always render every major section**, even if the content is “None expected.” That consistency makes it easier for humans, coding agents, and tests.

I recommend this exact format:

```markdown
# <Feature Title>

## Feature Summary
- One paragraph summary of the request and intended outcome.

## Assumptions
- Bullet list of assumptions.
- Explicit unknowns that need confirmation.

## Relevant Architecture
- Summary of the current architecture relevant to this change.

## Files Reviewed
| Path | Why It Matters | Confidence |
|------|----------------|------------|

## Files Likely To Modify
| Path | Expected Change | Reason |
|------|-----------------|--------|

## Data Model Changes
- Tables, schemas, models, migrations, serialization changes.

## API And Service Changes
- Endpoints, background jobs, services, auth, integrations.

## UI Changes
- Components, routes, forms, states, copy, or “None expected”.

## Implementation Phases

### Phase A
**Goal**
...
**Likely files**
...
**Tasks**
...
**Acceptance criteria**
...
**Validation**
...

### Phase B
...

## Risks
- Technical risks
- Product/integration risks
- Rollback concerns

## Test Plan
- Unit tests
- Integration tests
- End-to-end/manual checks
- Regression tests

## Claude Code Prompts

### Prompt For Phase A
```text
...
```

### Prompt For Phase B
```text
...
```

## Definition Of Done
- Checklist of completion criteria

## Generation Metadata
- Provider
- Model
- Repo root
- Timestamp
- Ranked file count
```

A few design choices matter here:

- **Files Reviewed** is your anti-hallucination anchor.
- **Files Likely To Modify** is the actionable handoff.
- **Assumptions** makes uncertainty visible instead of burying it.
- **Generation Metadata** helps with debugging, demos, and model comparisons later.
- **Claude Code Prompts** should be rendered from the structured phase objects, not generated in a second free-form pass.

## Repository analysis and planning workflow

### Repository Analysis Strategy

The V1 repository-analysis strategy should be **Git-aware, deterministic, and aggressively scope-controlled**, not “smart” in an overengineered sense.

The primary discovery path should be:

```bash
git ls-files --cached --others --exclude-standard --full-name -z
```

This is the cleanest V1 move because Git documents that `git ls-files` can merge tracked and working-tree files, `--cached` shows tracked files, `--others` shows untracked files, and `--exclude-standard` applies standard exclusions from `.gitignore`, `.git/info/exclude`, and the user’s global excludes. Git also documents that `.gitignore` affects intentionally untracked files and **does not** affect already tracked files, which is exactly the distinction you want when analyzing a real repository rather than a folder of files. citeturn11view0turn8view0

Fallback behavior should be: walk the filesystem and apply **PathSpec’s `GitIgnoreSpec`**. PathSpec explicitly documents GitIgnoreSpec as a way to replicate `.gitignore` behavior, including some Git edge cases where actual behavior differs from simplified documentation. That makes it the right fallback if Git is unavailable or if the folder is not a Git repository. citeturn8view1turn1search5

On top of Git-native ignore behavior, codegraft should maintain a small built-in denylist for things that should **never** enter model context unless the user aggressively overrides it:

- `.env*`
- `*.pem`
- `*.key`
- private key files
- certs and credentials
- state files
- binary blobs
- generated bundles
- minified assets
- very large files
- dependency/vendor directories

That is not paranoia. GitHub’s secret scanning docs describe hardcoded credentials and secret sprawl as a real repository risk. Anthropic and OpenAI both document business/API data controls and zero-data-retention options, but the safer engineering posture is still to avoid sending sensitive or unnecessary material in the first place. V1 should therefore be **local-first, selective-snippet, least-context** by design. citeturn13search2turn13search0turn16view0turn16view1

For codebase structure analysis, do not build a full language server. V1 only needs a compact inventory:

- root manifests and config files
- depth-limited directory tree
- primary language guess
- framework hints
- likely entry points
- existing test layout
- migration or schema directories
- CI/build/test commands inferred from manifests where obvious

This is enough to support a planning model call, and it is much less scope than full semantic indexing.

For file-type detection, keep it lightweight:

- extension-based mapping first
- shebang detection for extensionless scripts
- special-case well-known files like `Dockerfile`, `Makefile`, `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`

For relevant-file ranking, use a deterministic score, not an LLM:

```text
score =
  path token overlap
+ content keyword hits
+ symbol-name overlap
+ framework-role boost
+ proximity-to-manifest-or-entrypoint
+ test-convention boost
- generated/noise penalty
- oversized-file penalty
```

Concrete ranking heuristics for V1:

- Extract normalized keywords from the feature request.
- Boost filename and path overlap first.
- Search for request keywords in file content.
- Boost likely architectural roles:
  - `routes`, `controllers`, `handlers`, `views`
  - `services`, `use_cases`, `domain`
  - `models`, `schemas`, `migrations`
  - related tests
- Always consider root manifests and the project README.
- Add a diversity penalty so top results are not all from one folder.

This is the point where tools such as Aider and Cody are useful reference points. Aider explicitly talks about concise repository maps that help models reason about larger repos, and Cody emphasizes codebase context pulled from search and usage patterns. Those are signs that **context selection is the core engineering problem** here. For V1, you are not trying to equal those systems; you are borrowing the lesson that a model needs the right *subset* of repo information, not the whole repo. citeturn8view9turn9view0

For snippet extraction, I recommend this hierarchy:

- file header and imports
- top-level definitions if cheaply extractable
- windows around keyword hits
- short neighboring code windows
- a final hard cap per file and per request

Good default caps for V1:

- max ranked files: 12
- max lines per file snippet: 160
- max total context budget: 40k–60k characters
- skip files above 180 KB unless explicitly included

That size discipline is also consistent with the existence of repo-packers like Gitingest, which prominently cap included file size, and Repomix, which treats prompt-friendly packaging and token count as first-class concerns. Those tools are useful proof that **token discipline is part of the product**, not an implementation detail. citeturn8view8turn8view7

For large repositories, V1 should degrade gracefully instead of pretending to solve enterprise-scale code understanding. My recommendation:

- under ~500 candidate files: normal mode
- ~500–2500 candidate files: medium mode, stricter ranking and snippet caps
- above ~2500 candidate files: large-repo mode  
  - include root manifests and tree
  - rank fewer files
  - warn the user
  - recommend `--subdir`
  - optionally require confirmation before a paid model call

This is where you should explicitly **not** chase tree-sitter, embeddings, or project maps in V1. Tree-sitter is a parser generator and incremental parsing library intended for robust syntax trees across languages, and tools like Plandex explicitly use tree-sitter project maps for large-project understanding. That is valuable, but it is beyond the scope of a disciplined weekend V1. citeturn10view0turn18view4

### AI Planning Strategy

The right V1 tradeoff is **two-pass hybrid**, but with **only one expensive model call by default**.

That means:

- **Pass one:** deterministic local analysis  
  Repo discovery, filtering, ranking, snippet extraction, compact repo summary.

- **Pass two:** one schema-constrained planning call  
  The provider returns a typed `ImplementationPlan`.

- **Post-pass:** deterministic rendering  
  Markdown plan and Claude Code prompts are rendered from the plan object.

I would **not** ship V1 as a one-shot “send the repo and ask for a plan.” GitHub’s own Spec Kit docs frame spec-driven work as multi-step refinement rather than one-shot prompting, and Claude Code’s docs repeatedly push explore-first and plan-before-editing workflows. Even if codegraft is much lighter weight than Spec Kit, the correct design principle is the same: **separate context assembly from planning.** citeturn18view1turn18view2turn19view0turn20view0

I would also **not** ship V1 as planner + reviewer + test analyst + prompt generator. Claude Code does document subagents and even an adversarial review step as useful patterns, but that is the kind of orchestration that can easily overtake the product itself. V1 should reserve that for a later optional mode. citeturn20view1turn20view2

The best V1 prompt flow is:

1. Build a deterministic context bundle.
2. Send one planning prompt with:
   - feature request
   - repo summary
   - directory tree
   - files reviewed
   - targeted snippets
   - output rubric
   - output schema
3. Parse the result into `ImplementationPlan`.
4. Render Markdown.
5. Render Claude Code prompts from the plan phases.

That approach is strongly supported by current provider capabilities. Anthropic recommends XML tags for structured prompt sections and now supports structured outputs for validated JSON; OpenAI likewise supports JSON Schema-constrained Structured Outputs. In other words, the infrastructure now exists to make a typed-plan architecture the default V1 move rather than a speculative future enhancement. citeturn9view3turn8view5turn9view4

A V1.1 or V2 reviewer mode can be extremely narrow:

- read a generated plan
- read a git diff
- compare planned files vs changed files
- report obvious mismatches or missing tests

That idea also aligns nicely with Claude Code’s documented “review the diff against the plan” pattern, but it should be treated as a follow-on, not part of weekend scope. citeturn20view2

## Claude Code build phases

### Claude Code Execution Phases

For the architecture-heavy phases below, use **Claude Code plan mode** first, then approve edits once the plan is sane. Claude Code explicitly documents plan mode as a way to review changes before they touch disk. citeturn20view0

#### Foundation and contract

**Goal**  
Create the project skeleton, typed config, domain models, and a fake end-to-end plan path so the app can write a sample Markdown plan before any repository logic exists.

**Likely files/modules**  
`pyproject.toml`, `README.md`, `CLAUDE.md`, `src/codegraft/cli.py`, `src/codegraft/config.py`, `src/codegraft/models/plan.py`, `src/codegraft/planning/renderer.py`, `tests/test_cli.py`

**Acceptance criteria**  
You can run `codegraft plan "test request"` and get a stub Markdown file into `/plans`. The project has a clear `CLAUDE.md` with commands, scope guardrails, and architecture notes. Typer command help works.

**Suggested Claude Code prompt**

```text
We are building a Python CLI called codegraft.

Phase goal:
- scaffold the package structure
- add Typer CLI commands: init, inspect, plan
- add typed Pydantic models for config and ImplementationPlan
- add a stub renderer that writes a sample Markdown plan to /plans
- add a project CLAUDE.md with build/test commands and V1 guardrails

Constraints:
- do not add provider logic yet
- do not add repo scanning yet
- keep all code small and typed
- add basic CLI tests

Before editing, inspect the repo and propose a short implementation plan.
Then implement only this phase.
```

**Validation steps**  
Run CLI help, run the stub `plan` command, confirm file output, run tests.

**Rollback and scope-control notes**  
If you feel tempted to build “real” planning logic here, stop. The point of this phase is to lock the contract, not sophistication.

#### Discovery and ignore engine

**Goal**  
Implement Git-aware repository discovery, ignore handling, basic safety filtering, and file metadata collection.

**Likely files/modules**  
`src/codegraft/repo/discover.py`, `git_scan.py`, `ignore.py`, `safety.py`, `models/repo.py`, `tests/test_discovery.py`, `tests/test_ignore.py`, fixture repos

**Acceptance criteria**  
For fixture repos, the scanner returns tracked and untracked files as expected, respects nested `.gitignore` logic, and excludes secret-like/binary/oversized files.

**Suggested Claude Code prompt**

```text
Implement codegraft repository discovery and ignore handling.

Requirements:
- prefer git ls-files --cached --others --exclude-standard when git is available
- add filesystem fallback using PathSpec GitIgnoreSpec
- exclude obvious secrets, binaries, generated files, and oversized files
- return typed file metadata objects
- add fixture-based tests for nested .gitignore and denylist behavior

Constraints:
- do not rank files yet
- do not call any LLM provider
- keep the public interface simple and deterministic
```

**Validation steps**  
Run repo-discovery tests. Print discovered file counts on fixture repos. Manually inspect one real repo.

**Rollback and scope-control notes**  
Do not add semantic indexing, AST parsing, or caching here.

#### Repo summary, ranking, and snippet extraction

**Goal**  
Teach codegraft to summarize a repo, rank likely relevant files for a request, and extract bounded context snippets.

**Likely files/modules**  
`src/codegraft/repo/tree.py`, `detect.py`, `summarize.py`, `rank.py`, `snippets.py`, `cli.py`, `tests/test_rank.py`, `tests/test_snippets.py`

**Acceptance criteria**  
Given a fixture repo and request, codegraft returns a compact tree, detects likely stack/framework, ranks reasonable files near the top, and emits bounded snippets under budget.

**Suggested Claude Code prompt**

```text
Implement the deterministic analysis layer for codegraft.

Requirements:
- generate a compact repo tree summary
- detect primary languages and key manifests
- rank relevant files for a feature request using deterministic heuristics
- extract context snippets under configurable budgets
- add an inspect command that prints ranked files and scores

Constraints:
- no provider calls yet
- no embeddings
- no AST work unless a tiny stdlib-only Python helper is truly necessary
- write fixture-based tests for ranking quality
```

**Validation steps**  
Run `codegraft inspect "add RBAC to admin API"` on fixture repos. Check the top ten ranked files by hand. Run tests.

**Rollback and scope-control notes**  
If ranking is weak, improve heuristics and debug output before reaching for LLM reranking.

#### Anthropic planning core

**Goal**  
Add the first real provider, prompt assembly, structured plan generation, and schema validation.

**Likely files/modules**  
`src/codegraft/providers/base.py`, `anthropic_provider.py`, `src/codegraft/prompts/*`, `src/codegraft/planning/service.py`, `tests/test_providers.py`

**Acceptance criteria**  
With a real Anthropic API key, codegraft can generate a validated `ImplementationPlan` from a repository context bundle. With mocks, provider tests pass consistently.

**Suggested Claude Code prompt**

```text
Implement the first real planning provider for codegraft using Anthropic.

Requirements:
- create a PlanProvider abstraction
- implement Anthropic provider
- assemble prompts with XML-tagged sections
- request structured output matching the ImplementationPlan schema
- validate and parse the result into Pydantic models
- add mocked provider tests and one optional live integration test marker

Constraints:
- keep Anthropic-specific details inside the provider adapter
- do not render final Markdown in the provider
- fail loudly on malformed responses
```

**Validation steps**  
Run mocked tests. Generate one live plan against the demo repo. Confirm schema validation and error messages.

**Rollback and scope-control notes**  
Do not add a reviewer loop or model-comparison feature yet.

#### Markdown rendering and handoff prompts

**Goal**  
Turn the structured plan into polished Markdown and deterministic Claude Code prompts.

**Likely files/modules**  
`src/codegraft/planning/renderer.py`, `filenames.py`, `cli.py`, `tests/test_renderer.py`, `examples/sample_plans`

**Acceptance criteria**  
Generated Markdown always contains the required sections, writes into `/plans`, and includes phased Claude Code prompts with acceptance criteria and validation instructions.

**Suggested Claude Code prompt**

```text
Implement markdown rendering for codegraft.

Requirements:
- render all required sections in a stable format
- always include Files Reviewed, Risks, Test Plan, Claude Code Prompts, and Definition of Done
- write plans to /plans with timestamped filenames
- add snapshot-style tests for rendered markdown
- make Claude Code prompts deterministic from phase data, not a second LLM call

Constraints:
- keep formatting simple and readable
- prefer explicit 'None expected' over missing sections
```

**Validation steps**  
Render sample plans from fixtures. Check readability. Run renderer tests.

**Rollback and scope-control notes**  
Do not spend time on rich HTML output, PDFs, or docs-site generation.

#### OpenAI provider and polish

**Goal**  
Add OpenAI parity, final debug surfaces, demo assets, and README polish.

**Likely files/modules**  
`src/codegraft/providers/openai_provider.py`, `README.md`, `docs/screenshots`, `examples/demo_requests`, `examples/sample_plans`, tests

**Acceptance criteria**  
OpenAI provider works behind the same `PlanProvider` interface. README clearly explains the product, shows a sample run, and includes screenshots/example output. The project feels presentable.

**Suggested Claude Code prompt**

```text
Polish codegraft for V1.

Requirements:
- add an OpenAI provider using the same PlanProvider contract
- add debug output options for selected files and raw plan JSON
- create a demo request and sample output
- improve the README with installation, quickstart, architecture, limitations, and screenshots
- keep the scope local-first and CLI-first

Constraints:
- no web UI
- no hosted backend
- no diff validation
- no new architecture layers unless they directly support V1
```

**Validation steps**  
Generate one plan with each provider. Re-run full test suite. Review README with a “cold reader” eye.

**Rollback and scope-control notes**  
If time runs short, ship Anthropic-first and note OpenAI as next-in-line.

### Recommended Build Order

The exact order I recommend is:

1. Create the package skeleton, commands, and typed plan/config models.
2. Add a fake end-to-end `plan` path that writes a stub Markdown file.
3. Create `CLAUDE.md` for the codegraft project with phase guardrails and test commands.
4. Implement Git-aware repository discovery.
5. Add fallback ignore logic with PathSpec.
6. Add safety filtering for secrets, binaries, and huge files.
7. Add repo summary and compact tree generation.
8. Add deterministic relevant-file ranking.
9. Add snippet extraction and budget enforcement.
10. Implement the Anthropic provider.
11. Add structured output parsing into `ImplementationPlan`.
12. Render final Markdown and Claude Code prompts.
13. Add `inspect` and debug artifacts.
14. Add the OpenAI provider.
15. Build fixture repos and tests.
16. Add demo request, sample output, screenshots, and README polish.

That order is deliberately **golden-path first**. You want a complete vertical slice early, then improve discovery and quality, not the other way around.

### Estimated Build Effort

These are my estimates, not sourced facts:

**Barebones MVP**  
About **8–12 hours**. That version would include one provider, scanner, ranking, snippets, and Markdown output, but only minimal tests and minimal polish.

**Polished V1**  
About **16–24 hours**. This includes the `inspect` surface, strong README, demo artifacts, fixture repos, snapshot tests, and enough architecture quality to explain clearly.

**Likely Claude Code usage relative to the recipe app**  
Roughly **2x–3x the recipe app’s Claude usage**. If the recipe app took ~20% of your weekly limit, I would budget **40%–60%** for a polished codegraft V1. The reason is not UI complexity; it is repeated architecture iteration, test fixture work, and prompt/ranking tuning.

**Likely number of Claude Code sessions or prompt cycles**  
About **8–12 focused sessions**, or roughly **35–60 substantial prompts**, depending on how much you let Claude wander.

**Likely friction points**

- ranking initially feels too naive
- snippet extraction includes the wrong evidence
- prompt output feels generic rather than codebase-aware
- malformed or incomplete model output if you try to cheat the schema
- README polish takes longer than expected
- fixture repos expose ignore-rule edge cases

**Weekend feasibility**  
Yes, for a **focused** weekend. My practical recommendation would be:

- **Day one:** skeleton, scanner, ranking, snippets
- **Day two:** Anthropic provider, Markdown output, tests, sample run
- **Late polish block:** README, screenshots, OpenAI provider if time remains

If your weekend time is fragmented, split it into **core V1** and **polish V1.1** instead of trying to cram both.

## Risks, testing, and scope control

### Risk Analysis

The biggest V1 risks are not abstract “AI risk.” They are very specific: malformed plan output, bad context selection, overly large prompts, and privacy/cost mistakes. Structured outputs help with format reliability, Claude Code docs explicitly warn that long context degrades performance, and Anthropic exposes token counting and prompt caching tooling that make budget-awareness a real engineering concern rather than a theoretical one. citeturn8view5turn9view4turn19view0turn9view2turn9view1

A second risk bucket is privacy and accidental data exposure. Both OpenAI and Anthropic document business/API data controls and zero-data-retention variants for eligible customers, but V1 should still assume the safest posture is **local analysis + selective snippets + explicit secret filtering**. GitHub’s secret-scanning docs are a useful reminder that repositories do contain credentials more often than teams expect. citeturn16view0turn16view1turn13search2turn13search0

Here is the V1 risk matrix I would use:

| Risk | Why it matters | V1 mitigation |
|---|---|---|
| LLM hallucination about repo structure | Produces confident but wrong plans | Require `Files Reviewed`, separate `Assumptions`, and never let the model invent reviewed files not in the context bundle |
| Context selection failure | Good model, bad evidence | Add `inspect`, show ranked files and scores, include manifests/README by rule, allow `--include` and `--subdir` |
| Token blowups | Higher cost, lower quality | Hard caps on candidate files, snippet size, and total context; prefer snippets over full files |
| Large repo limits | Weak results on monorepos | Warn early, degrade gracefully, recommend subdirectory scoping, explicitly document large-repo limits |
| Prompt quality drift | Generic or repetitive plans | Version prompt templates, keep one schema, store example outputs, add snapshot tests |
| API key handling | Accidental exposure in logs or outputs | Read from env/`.env`, never render env values, exclude `.env*`, redact debug artifacts |
| Cost creep | Repeated planning runs can add up | One main model call by default, low temperature, optional review off by default, surface provider/model in config |
| Output quality validation | Plan looks polished but is not useful | Use fixture repos, golden sample requests, renderer snapshots, and one manual sample review before calling V1 done |

The most important mitigation philosophy is simple: **make the plan explainable**. If you can show what files were considered, which were selected, and why, you can debug most of the system without guessing.

### Testing Strategy

Yes: **use mocked LLM responses for the vast majority of tests**.

You want three layers of tests:

**Deterministic unit and fixture tests**

- repo scanning
- nested ignore logic
- secret and binary exclusion
- large-file filtering
- language and manifest detection
- tree generation
- ranking heuristics
- snippet extraction
- filename generation

These should use small fixture repos checked into `tests/fixtures/`.

**Contract and rendering tests**

- prompt construction from deterministic context bundles
- provider adapter request shape
- plan parsing into `ImplementationPlan`
- Markdown rendering snapshots
- Claude Code prompt rendering snapshots

These should mostly use mocked provider responses.

**Thin live integration tests**

- Anthropic live smoke test
- OpenAI live smoke test

These should be opt-in only, maybe behind markers such as:

- `pytest -m live_anthropic`
- `pytest -m live_openai`

I would specifically test the following behaviors:

- scanner returns tracked + untracked while respecting ignores
- tracked files still appear even if ignore patterns match them
- top-ranked files are sensible for known feature requests
- snippet budgets do not exceed configured limits
- renderer always emits every required Markdown section
- provider adapters surface clear errors for missing keys and invalid models
- CLI exits with useful messages on repo path problems and provider failures

For CLI behavior, use Typer’s testing support through Click-compatible command testing patterns; for providers, keep the live calls minimal and rely on mocked, schema-shaped outputs for repeatable CI.

A good test target for V1 is not “high coverage.” It is **confidence in the deterministic pipeline**. If the deterministic pieces are solid, the live model behavior becomes much easier to troubleshoot.

### Final V1 Definition of Done

codegraft V1 is done when all of the following are true:

- `codegraft plan` works on at least one real repository and one fixture repo.
- The scanner respects Git-aware ignore behavior and excludes secret-like/binary/noise files.
- The tool produces a compact repo summary and ranked relevant files.
- The context bundle stays under configured limits.
- Anthropic provider works end to end.
- The plan is parsed into a typed schema before rendering.
- The Markdown output lands in `/plans`.
- The Markdown output includes all required sections every time.
- Claude Code prompts are rendered phase by phase.
- There is at least one believable demo request and one checked-in sample plan.
- `codegraft inspect` exists and is useful.
- Core repo-analysis tests pass.
- Markdown snapshot tests pass.
- CLI tests pass.
- README explains installation, usage, architecture, and limitations.
- Screenshots or terminal captures exist.
- You can explain the tradeoffs clearly without hand-waving.

### Deep Scope Guardrails

These are the features I would explicitly refuse in V1, even if they are tempting:

- “Let codegraft directly edit code.”
- “Let codegraft run Claude Code automatically.”
- “Add a web app so it looks more impressive.”
- “Add auth, users, projects, history, sharing, and cloud sync.”
- “Add vector search so it feels more AI-native.”
- “Add tree-sitter everywhere.”
- “Add agent teams for planning and review.”
- “Add codebase chat.”
- “Add remote GitHub repo support.”
- “Add diff validation against the plan.”
- “Add persistent project memory.”
- “Add benchmark dashboards across many models.”

If a new idea does not make the **single-run local planning pipeline** noticeably better, it goes to V2, not V1.

## Positioning and README story

### Polish Plan

The README should tell a very clear story:

- the problem
- the wedge
- the workflow
- the architecture
- the demo
- the tradeoffs

A strong README structure would be:

1. One-paragraph pitch  
   “codegraft turns a feature request plus a local repository into a structured implementation plan for coding agents.”

2. Why this exists  
   Short explanation of brownfield planning pain and why coding agents need bounded context and plans.

3. Quickstart  
   Install, set `.env`, run `codegraft inspect`, run `codegraft plan`.

4. Example input and output  
   Show one feature request and one slice of a generated plan.

5. How it works  
   Repo discovery → ranking → context bundle → structured plan → Markdown.

6. Architecture notes  
   Typed plan schema, provider abstraction, deterministic analysis layer.

7. Limitations  
   Large monorepos, no diff validation, no embeddings, no remote repos.

8. Roadmap  
   Focused V2 items only.

For screenshots, I would include exactly three:

- an `inspect` output with ranked files
- a `plan` command run finishing and writing to `/plans`
- an excerpt from a generated Markdown plan showing phases, risks, and test plan

For the sample demo repository, use **one small backend-heavy repo** rather than a toy string processor. A small FastAPI or Express-style service with models, routes, services, migrations, and tests is ideal. The demo feature request should force the tool to reason about architecture, not just filenames. Good examples:

- “Add organization-scoped API keys and audit logging.”
- “Add role-based access control to admin routes.”
- “Add soft-delete support and restore endpoints for recipes.”

That kind of example exercises real architectural reasoning, not just filename matching.

For an architecture diagram, keep it simple:

- **left to right:** repo + request → analysis → structured plan → Markdown
- annotate where logic is deterministic and where the LLM is used
- call out privacy boundary: raw repo stays local, selected snippets only leave the machine

Position it as more than “a CLI that calls Claude.” It is:

- a **brownfield planning system**
- with **deterministic context assembly**
- a **typed output contract**
- a **provider abstraction**
- and a **practical agent handoff artifact**

That is how you avoid the shallow-wrapper impression.

The broader landscape helps this story. Since repo-packers, spec kits, and full autonomous agents already exist, your differentiation is the **local-first, evidence-backed implementation-plan wedge** rather than generic “AI devtool” branding. citeturn8view8turn8view7turn18view0turn18view2turn18view4

