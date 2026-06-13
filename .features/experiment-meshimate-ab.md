# Experiment: MeshiMate A/B — does a codegraft plan help execution?

First real-world test of codegraft's output, run 2026-06-12 on the MeshiMate
repo (a React Native / Expo app, separate from codegraft). Retest scheduled for
2026-06-13 after the planner-prompt change this finding motivated.

## Setup

Same feature, two Claude Code execution sessions:
- **Plan group:** prompted with the codegraft-generated plan
  (`2026-06-12-...add-categories-tags-and-com.md`).
- **Control group:** prompted with the same one-line request used to *generate*
  that plan ("user should be able to add categories, tags, and components" from
  Settings).

Feature: add an "Add" capability to the three vocabulary-management screens
(Categories/Tags/Components), which all delegate to a shared
`TaxonomyManagementScreen`.

Plan generation cost: **~$0.15** on `claude-sonnet-4-6` (output-dominated; input
stayed small thanks to selective context — ~9.9k snippet tokens, ~169k
"saved" vs dumping all candidate files).

## What was measured, and the surprising result

The only available proxy was Claude Code's **context-window token usage**:
- Plan group: Messages **68.7k** (~81.4k total before opening a PR)
- Control group: Messages **50.7k** (~70.2k total)

**The plan group used MORE context (~18k / ~35% more Messages), not less.**

### Why "more" is not "worse" here
- The plan itself is ~4–5k tokens sitting in context.
- The plan *prescribes thorough work* (read the central file, audit all repos,
  run tests, verify in 3 places) — rigor costs tokens.
- Measurement stages weren't perfectly matched.
- **Most important:** token count was never codegraft's claim. The ~169k savings
  is about generating the plan cheaply (the *planning* call), not about making
  the *execution* agent cheaper. The A/B accidentally tested a different
  hypothesis ("does a handoff plan reduce executor context?") and the answer,
  for a strong agentic executor on a small repo, was **no**.

## The real finding (from comparing the actual code)

The two `TaxonomyManagementScreen.tsx` implementations were ~95% identical, but
diverged in one meaningful way — how they modeled the add/rename UI:

| | Plan version | Control (one-liner) |
|---|---|---|
| Modal design | **two** parallel modals (add + rename), duplicated state/handlers | **one** unified name-editor with a `mode: 'add'\|'rename'` switch |
| State vars | 6 | 3 |
| File length | 443 lines | 388 lines |
| Local elegance | adequate, repetitive | **cleaner / DRYer / more maintainable** |
| Error handling | inconsistent (rethrow on rename, swallow on add) | consistent |
| Component test | **added** (guards `isUserCreated=true` invariant) | none |
| Settings copy | **updated** ("Create and manage…") | unchanged |

So it was a genuine split:
- **Control won on local code elegance** — Claude Code, unconstrained, spotted
  that "add" and "rename" are the same interaction and unified them.
- **Plan won on completeness/coverage** — it surfaced the `isUserCreated` domain
  invariant (in Assumptions/Open-Questions/acceptance-criteria) and turned it
  into a real test; it caught a now-inaccurate settings string.

### The deep insight
**A plan imprints its own decomposition onto the code.** The plan's Phase 2
prompt said "add an `onAdd` prop and an add modal" — so the agent added a
*parallel* add modal instead of refactoring the existing rename modal into a
shared editor. The plan's structure became the implementation's structure: good
for completeness, but it anchored the executor away from the cleaner refactor the
control group found freely.

Corollary observed in the wrappers: the plan told the wrapper screens to wrap the
create call in try/catch + Alert; the agent **ignored that** and let the shared
component own error handling (the better choice). Over-prescriptive prompts get
partially overridden anyway — and where they're followed, they can lock in a
weaker design.

## Action taken

Softened `prompts/planner_system.md` to be **goal-oriented, not structure-
prescriptive**, while preserving the completeness levers:
- New rule: describe each change by its goal/behaviour, name the files and
  outcome, but don't dictate internal structure (components/props/state).
- New rule: when a change resembles existing code, prefer extending/unifying over
  a parallel copy.
- Reworded the handoff-prompt rule to frame prompts around outcomes + existing
  patterns, not rigid step-by-step.
- **Preserved verbatim:** anti-hallucination anchor, Assumptions/Open-Questions,
  Test Plan, validation steps, Definition of Done — these produced the plan's
  wins (the invariant + the test) and must stay.

Locked in by `test_prompt_favours_goal_over_structure_and_reuse`.

## Tension to watch
Prescriptiveness *helps weak executors*, and codegraft's value is highest for
weak/automated executors. The change soften only *internal-structure* dictation;
files, behaviour, and tests stay concrete — and the reuse hint actually helps a
weak executor (it says what to mirror). If a future test shows weak executors
now flail, dial the structure guidance back up.

## Open questions / next tests
- **Retest the same feature** after the prompt change: do the generated handoff
  prompts now describe goals + invite reuse rather than prescribe parallel
  structure? (2026-06-13)
- **Test where the executor is the weak link** — a cheaper/weaker execution
  model, or a large unfamiliar repo where exploration is expensive. That's the
  regime where a plan should pay off most; the small-repo + strong-executor case
  here is the *least* favourable for codegraft.
- The ranking gap that started this thread (`TaxonomyManagementScreen.tsx`, the
  central file, wasn't in the evidence bundle) → motivates an **import-graph
  proximity boost** in ranking: if several top-ranked files import X, pull X in.

## Bottom line
For a strong agentic executor on a small repo, a codegraft plan adds
**completeness and reviewability, not token savings or code elegance** — and can
mildly anchor the implementation. That's an honest, defensible positioning, and
it points at two concrete improvements (goal-oriented prompts: done;
import-graph ranking boost: open).
