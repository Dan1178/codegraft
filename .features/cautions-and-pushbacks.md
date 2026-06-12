# Cautions & pushbacks (carry across sessions)

My standing concerns on the CodeGraft blueprint. None of these are objections to
building it — they're where attention/iteration budget should go, and the
assumptions to verify rather than trust. Update as items are resolved.

## 1. Ranking quality is the whole ballgame
**Status: open — the core risk.**

Discovery, ignore, and safety filtering are plumbing you get right in an
afternoon. The project succeeds or fails on **relevant-file ranking**. Pure
lexical overlap is naive: "add RBAC" will match every file containing "user".

- Budget most of the *iteration* time here, not on the scanner.
- Lean hard on `inspect` as the debugging surface — show scores so weak ranking
  is visible and tunable.
- When ranking feels bad, fix heuristics + debug output **before** reaching for
  LLM reranking or embeddings (the latter is explicitly out of V1 scope).

## 2. The `ImplementationPlan` schema is large (15 fields, nested)
**Status: accepted for now — revisit at Phase 4.**

Big schemas can hurt structured-output reliability and inflate latency/cost.
Kept in full for Phase 1 because the model isn't called yet and locking the
contract is the point. When the real provider call lands:

- Watch for dropped/empty fields or malformed responses on the full schema.
- Be willing to ship a leaner core schema first and grow it once the round-trip
  is solid.

## 3. The ChatGPT research citations are unverifiable
**Status: RESOLVED (Phase 4).**

The load-bearing claim — "Anthropic supports schema-constrained structured
outputs" — was **confirmed** against the authoritative claude-api skill: real
support via `client.messages.parse(output_format=<Pydantic model>)` →
`.parsed_output`. No JSON-mode fallback was needed; the architecture held.

Implementation note: the strict schema forces the model to emit all fields,
including `metadata` — so codegraft **overwrites** `plan.metadata` after parsing
(the model is told to leave it empty, but provenance is authored by us
regardless). Other ChatGPT citations remain unverified but are non-load-bearing.

## 4. Windows / cross-platform reality
**Status: partially handled — stay vigilant.**

Already bit us in Phase 1: the legacy Windows console (cp1252) crashed on
`->`/`—` glyphs and would crash on any non-ASCII model output via `--stdout`.
Fixed by forcing UTF-8 streams + keeping our own console literals ASCII.

Remaining watch items:
- `git ls-files` subprocess calls: handle the `-z` NUL separator, `--full-name`
  paths, and decode as UTF-8 explicitly.
- Always pass `encoding="utf-8"` on file I/O (plans, snippets, config).
- Use `pathlib` everywhere; normalize separators when matching ignore patterns
  (PathSpec expects forward slashes).
- Don't assume POSIX-only shell behaviour anywhere in the pipeline.

## 5. Scope discipline is the report's best quality — protect it
**Status: ongoing.**

The blueprint is unusually disciplined; the failure mode is letting it drift
toward embeddings, tree-sitter project maps, diff validation, multi-agent
orchestration, or a web UI. The guardrails live in `CLAUDE.md`. Rule of thumb:
if an idea doesn't make the **single-run local planning pipeline** noticeably
better, it's V2.
