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
**Status: open — verify at Phase 4, don't trust blindly.**

The `turn8view8`-style citations are deep-research artifacts I can't check. The
load-bearing one is **"Anthropic supports schema-constrained structured
outputs."**

- Confirm the *actual* current Anthropic API capability before building the
  provider (use the claude-api skill / live docs, not the report's claim).
- The architecture survives either way: worst case we fall back to tool-use /
  JSON mode to get a validated `ImplementationPlan`.

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
