---
name: agentic-loop-review
description: >-
  Multi-phase post-implementation review: 5 parallel agents (Quality,
  Implementation, Testing, Documentation, Simplification) -> Fixer loop (max 5),
  then code smells, external review (opus, independent brief), critical-only.
  Use when the user says agentic-loop-review, review, agentic review, code
  smells, external review, critical review, or when agentic-loop-plan-exec /
  agentic-loop reaches the review phases.
---

# Review (agentic multi-phase)

Post-implementation multidimensional review. Inspired by cc-thingz + the Agent Review pattern.

**Models:** reviewers/fixer = `sonnet`; external = `opus` with an independent-reviewer brief.
Prefer the pinned `agentic-loop-*` subagents in `~/.claude/agents/` (models set in
frontmatter), invoked via the `Agent` tool with `subagent_type`.

After each review phase, emit a Stage report
(`~/.claude/skills/agentic-loop/references/stage-report.md`).

## When invoked

- After `agentic-loop-plan-exec` finishes tasks
- Standalone: review the current branch/diff against a plan (or HEAD vs default branch)

## Setup

1. Resolve the default branch (`main` / `master` / `trunk`).
2. Diff: `git diff <default>...HEAD` (else staged/unstaged).
3. Pass the plan path to reviewers when known.
4. Append phase notes to `/tmp/progress-<stem>.txt` if present.

## Phase 1 — Agent Review & Test (5 parallel -> Fixer loop)

Report: `--- Review phase 1: Agent Review (5 parallel) ---`

### Parallel reviewers (always all five, one message)

Launch from the **orchestrator (this session)** in **one** message with five `Agent` tool
calls (`run_in_background: false` so results return together):

| subagent_type | Focus |
|---------------|-------|
| `agentic-loop-quality` | Best practices |
| `agentic-loop-implementation` | Conformance to the plan |
| `agentic-loop-testing` | Coverage, edge cases |
| `agentic-loop-documentation` | Comments, docstrings |
| `agentic-loop-simplification` | Redundancy |

If the pinned subagents are unavailable, spawn 5x `general-purpose` with `model: sonnet` and
the prompts from [references/reviewers.md](references/reviewers.md).

### Then Fixer

1. Collect **full** outputs (do not filter or dismiss).
2. If **all five** report `NO ISSUES FOUND` / zero issues -> phase clean -> go to phase 2.
3. Else spawn `agentic-loop-fixer` (or `general-purpose` + [references/fixer.md](references/fixer.md))
   with the **verbatim** findings.
4. Show FIXES to the user.

### Loop: review -> fixer -> review

Repeat the **5 parallel reviewers -> fixer** cycle until:

- no problems found, **or**
- **max 5 iterations** reached (`review_iterations = 5`)

On iterations 2-5, still run all five reviewers (full multidimensional pass), then the fixer if
needed. If max iterations hit with remaining issues, report and continue to phase 2 — do not
silently drop findings; list the leftovers.

## Phase 2 — Code smells

Report: `--- Review phase 2: code smells ---`

1. One `Agent` (`general-purpose`, `model: sonnet`) with the smells prompt.
2. If findings -> `agentic-loop-fixer`.
3. Single pass, then continue.

## Phase 3 — External review (independent brief)

Report: `--- Review phase 3: external review (opus, independent) ---`

Use `agentic-loop-external-review` (`model: opus`). See the caveat in
`~/.claude/skills/agentic-loop/references/model-routing.md` — this is a fresh-context
adversarial pass, not a cross-family check.

Adversarial loop (max 5):

1. External review of the diff vs the plan; severities `CRITICAL` / `MAJOR` / `MINOR`.
2. `NO ISSUES FOUND` -> done.
3. Else -> fixer -> if no remaining CRITICAL/MAJOR after fixes, stop (minors fixed once).
4. If blocking issues remain -> loop.

## Phase 4 — Critical only

Report: `--- Review phase 4: critical/major only ---`

One pass: `agentic-loop-quality` + `agentic-loop-implementation` (critical/major only) ->
fixer if needed.

## Hard rules

- Fan-out from the **orchestrator** (this session), never from nested subagents
- Never dismiss findings as pre-existing — the fixer decides
- Pass findings verbatim to the fixer
- No push; commits only if the user explicitly asked
- Default `review_iterations = 5` for phase 1
