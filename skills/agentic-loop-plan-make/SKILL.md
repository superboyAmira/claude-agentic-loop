---
name: agentic-loop-plan-make
description: >-
  Create a structured implementation plan in docs/plans/yyyymmdd-<task>.md,
  persist planning dialogue under docs/agentic/, then plan-review with the
  agentic-loop-plan-review subagent. Use when the user says
  agentic-loop-plan-make, plan-make, write a plan, or after brainstorm's
  "Write plan".
---

# Plan Make

Create `docs/plans/yyyymmdd-<slug>.md` + session planning docs.
Inspired by [cc-thingz planning:make](https://github.com/umputun/cc-thingz).

## Model

Steps **0-2** parent: **Opus** (`/model opus`).
**Auto review (step 3):** `Agent` tool -> `subagent_type: agentic-loop-plan-review` (pinned to
`opus`).

## Documentation (mandatory)

Follow `~/.claude/skills/agentic-loop/references/session-docs.md`.

- Write `docs/agentic/yyyymmdd-<slug>/planning.md` with the full planning Q&A.
- Keep `needs-documenting.md` updated.
- Link the session folder from the plan Overview.
- The planning dialogue must not remain chat-only.

## Custom rules (optional)

`.claude/planning-rules.md` in the project (project wins).

## Step 0: Parse intent and gather context

Quick scan (< ~30s tool use):

1. Parse intent (feature / bug / refactor / migration / unclear).
2. Read/Glob/Grep only — no research subagent.
3. <= ~5 files; prefer manifest / CLAUDE / AGENTS / README / brainstorm.md.
4. 3-5 bullet context summary.

## Step 1: Questions (one at a time)

1. Main goal
2. Scope
3. Constraints
4. Testing: TDD vs code-first
5. Short title / slug

Record answers in `planning.md`.

## Step 1.5: Approaches

2-3 options with trade-offs unless obvious / already chosen in brainstorm. Record choice.

## Step 2: Write the plan file

1. `mkdir -p docs/plans docs/agentic/yyyymmdd-<slug>`
2. Create `docs/plans/yyyymmdd-<slug>.md` via
   [references/plan-template.md](references/plan-template.md).
3. Flush `planning.md` + update `needs-documenting.md`.
4. In the plan Overview, link `docs/agentic/yyyymmdd-<slug>/`.

Hard requirements: numbered tasks, Files blocks, tests as separate checkboxes, acceptance +
docs tasks at the end.

## Step 3: Plan review gate

| Option | Action |
|--------|--------|
| Auto review | `Agent` -> `agentic-loop-plan-review`. On `NEEDS REVISION`, fix plan + docs, re-ask |
| Revise with me | Interactive revision |
| Implement | -> `agentic-loop-plan-exec` |
| Done | Stop |

No coding in this skill. Stage report after plan-make and after plan-review.

## Principles

- One question at a time; YAGNI; lead with recommendation
- Plan file = source of truth for `agentic-loop-plan-exec`
