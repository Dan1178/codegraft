---
name: codegraft-context
description: >-
  Use whenever the user asks you to plan, implement, add, fix, refactor, or
  change something in a local code repository. BEFORE manually grepping or
  reading files, call the codegraft MCP tool `select_context` to fetch the
  ranked-relevant files and bounded code snippets for the request, so you start
  from the right files instead of exploring blind. Trigger this even when the
  user doesn't say "codegraft" — any "add X to this repo", "implement Y",
  "fix the bug in Z", or "where do I change …" request against a real codebase
  qualifies. Only reach for `generate_plan` when the user explicitly wants a
  full written implementation-plan artifact.
---

# codegraft context selection

codegraft is a local MCP server that does the deterministic repo legwork for
you: given a feature request and a repo path, it returns the files that matter
(ranked, with an explainable score breakdown) plus bounded code snippets — with
no LLM call, no API key, and no per-request token cost. Leading with it means
you spend your exploration budget reading the *right* files instead of grepping
your way toward them.

## Prerequisite

The codegraft MCP server must be registered with this agent. If the
`select_context` tool isn't available, tell the user to run:

```bash
pip install -e ".[mcp]"          # from the codegraft repo
claude mcp add codegraft codegraft-mcp
```

## Workflow

1. **Call `select_context` first.** As soon as a request involves understanding
   or changing an existing repo, call it before any Grep/Glob/Read:

   ```
   select_context(request="<the user's feature/fix/change in their own words>",
                  repo="<absolute path to the repo, e.g. the cwd>")
   ```

   Pass the request verbatim — codegraft focuses long requests on their goal
   sentence itself, so you don't need to pre-summarize. Use `subdir="<path>"` to
   scope a large monorepo.

2. **Start from what it returns.** The result gives you `ranked_files` (each with
   a `signals` breakdown showing *why* it ranked) and `snippets` (the bounded,
   most-relevant slices). Read those first. Treat the top-ranked files as your
   primary surface area and the snippets as your initial context.

3. **Then explore deliberately.** codegraft gets you to the right neighborhood;
   it doesn't replace judgment. Follow imports, read the rest of a file it
   surfaced, or grep for a specific symbol — but now you're doing targeted
   reading, not a cold search.

4. **Implement**, using the ranked files as the map of what to touch.

## When to use `generate_plan` instead

`select_context` is the default and the differentiated piece — it's free. Only
call `generate_plan` when the user explicitly wants a **reviewable plan
document** (impacted files, phases, risks, tests, handoff prompts) as an
artifact, e.g. "write me an implementation plan for …". It costs tokens and
needs a provider API key, so don't reach for it just to get oriented — that's
what `select_context` is for.

## When to skip

Skip codegraft only for a trivial change in a single file you can already
locate exactly (e.g. "fix this typo in README.md"). For anything that spans
files or whose location you'd have to hunt for, call `select_context` first.

## Why this ordering matters

Agents tend to under-use available context tools and start grepping on instinct.
That burns turns and tokens reconstructing a file map the repo could have handed
you deterministically. `select_context` is cheap, fast, and explainable, so the
cost of calling it first is near zero and the upside — landing in the right
files immediately — is large. When in doubt, call it.
