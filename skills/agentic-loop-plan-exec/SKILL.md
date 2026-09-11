---
name: agentic-loop-plan-exec
description: >-
  Execute a docs/plans/*.md plan task-by-task using isolated Agent subagents,
  then run multi-phase review via agentic-loop-review. Use when the user says
  agentic-loop-plan-exec, plan-exec, execute plan, run plan, or implement the
  plan autonomously.
---

# Plan Exec

Execute a plan file task-by-task. You are the **orchestrator** — subagents write code; you
track progress. Inspired by
[cc-thingz planning:exec](https://github.com/umputun/cc-thingz). Adapted for the Claude Code
`Agent` tool.

## Model

Agentic-loop **step 4+**. Prefer parent **Sonnet** here (execution phase — Opus is not needed).
Task implementers: `Agent` tool, `subagent_type: general-purpose`, `model: sonnet`.
Fixer: `subagent_type: agentic-loop-fixer`.
After tasks, hand off to the `agentic-loop-review` skill (5 parallel reviewers -> fixer,
max 5 iterations; external review on `opus`).

## Arguments

Optional path to a plan. If omitted: list `docs/plans/*.md` excluding `completed/`. If one
file — use it. If many — ask the user to pick.

## Config defaults

| Key | Default |
|-----|---------|
| `task_retries` | 1 |
| `review_iterations` | 5 |
| `commit_per_task` | false (ask once at start; respect user git rules) |
| `plans_dir` | `docs/plans` |

## Process

### 1. Resolve plan

Read the plan. Count `### Task N:` / `### Iteration N:` sections.

### 2. Isolation / branch

Ask once:

- Stay on current branch / create feature branch from the plan slug (strip date prefix:
  `20260722-foo` -> `foo`)
- Default: create/use a feature branch **in-place** (no worktree unless the user asks)

Do not push. Create commits only if the user explicitly allows `commit_per_task` (or asks to
commit).

### 3. Todo list

Create task/todo items (TaskCreate or TodoWrite): one per plan Task + `Review phases` +
`Docs & PR handoff`.

### 4. Progress file

Create `/tmp/progress-<plan-stem>.txt` with a header (plan path, branch, start time). Append
short phase notes as you go. Do not dump huge logs.

### 5. Task loop (sequential — NEVER parallel)

Repeat until no `[ ]` remain in any Task section (max 50 iterations):

1. Re-read the plan file
2. Find the first Task section with remaining `[ ]`
3. Announce to the user: task title + unchecked items
4. Spawn **one** `Agent` subagent (`general-purpose`, `model: sonnet`) with the prompt from
   [references/task-prompt.md](references/task-prompt.md)
5. Wait for it to finish before starting the next
6. Re-read the plan — if that task's checkboxes are not all `[x]`, retry up to `task_retries`
7. Report one line: `Task N completed` (or failure)

**The orchestrator must not** implement, debug, or fix code itself. Retry with a fresh
subagent and pass the error details.

### 6. Reviews

When all task checkboxes are done, read and follow
`~/.claude/skills/agentic-loop-review/SKILL.md` for phases:

1. Agent review (5 parallel -> fixer loop)
2. Code smells -> fixer
3. External review (`opus`, independent brief) -> fixer
4. Critical-only review -> fixer

### 7. Completion

- Collect `[decision]` / `[deviation]` lines from the progress file; show them to the user
- Ask whether to run `agentic-loop-docs-pr` next
- Do **not** push; do **not** move the plan to `completed/` until reviews finish and the user
  agrees (or docs-pr does it)

## Hard rules

- One task subagent at a time
- Plan file is the source of truth — always re-read
- Never dismiss review findings as "pre-existing" — pass full findings to the fixer
- Subagents must not ask the user questions; they log `[decision]` / `[deviation]` instead
- No commits unless the user opted in

## Telemetry

After each completed plan task and after the review handoff, emit a Stage report:
`~/.claude/skills/agentic-loop/references/stage-report.md`.
