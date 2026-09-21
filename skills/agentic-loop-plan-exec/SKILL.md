---
name: agentic-loop-plan-exec
description: >-
  Execute a docs/plans/*.md plan task-by-task using isolated Agent subagents,
  with a deterministic verify gate after every task and before reviews, then
  run multi-phase review via agentic-loop-review. Use when the user says
  agentic-loop-plan-exec, plan-exec, execute plan, run plan, or implement the
  plan autonomously.
---

# Plan Exec

Execute a plan file task-by-task. You are the **orchestrator** — subagents write code; you
track progress and run the verify gate. Inspired by
[cc-thingz planning:exec](https://github.com/umputun/cc-thingz). Adapted for the Claude Code
`Agent` tool.

## Model

Agentic-loop **step 4 and 4.5**. The parent does not need the `planner` model here; the
`executor` model is enough. Task implementers: `Agent` tool, `subagent_type: general-purpose`,
`model: <executor>`. Fixer: `subagent_type: agentic-loop-fixer`. Roles resolve in
`~/.claude/skills/agentic-loop/references/model-routing.md`.
After tasks and a green gate, hand off to the `agentic-loop-review` skill.

## Arguments

Optional path to a plan. If omitted: list `docs/plans/*.md` excluding `completed/`. If one
file — use it. If many — ask the user to pick.

## Config

Caps (`task_retries`, `task_loop_iterations`, `verify_repairs`) come from
`~/.claude/skills/agentic-loop/references/limits.md` and are enforced with `loop-state.py bump`.

| Key | Default |
|-----|---------|
| `commit_per_task` | false (ask once at start; respect user git rules) |
| `plans_dir` | `docs/plans` |

```bash
L=~/.claude/agentic-loop/bin
```

## Process

### 1. Resolve plan and state

Read the plan. Count `### Task N:` / `### Iteration N:` sections. If `.llm/loop-state.json`
is missing (standalone run), `python3 $L/loop-state.py init --session <plan stem> --entry from-plan`.
`loop-state.py set --plan <path>`; `loop-state.py step 4 in_progress`.
No `.llm/verify.json` -> `verify-gate.py init` and confirm the steps with the user before task 1.

### 2. Isolation / branch

Ask once:

- Stay on current branch / create feature branch from the plan slug (strip date prefix:
  `20260722-foo` -> `foo`)
- Default: create/use a feature branch **in-place** (no worktree unless the user asks)

`loop-state.py set --branch <b>`. Do not push. Create commits only if the user explicitly allows
`commit_per_task` (or asks to commit).

### 3. Todo list

Create task/todo items (TaskCreate or TodoWrite): one per plan Task + `Verify gate` +
`Review phases` + `Docs & PR handoff`.

### 4. Progress file

Create `docs/agentic/<session>/progress.md` (see session-docs.md) with a header (plan path,
branch, start time). Append short phase notes as you go. No logs - they live in `.llm/verify/`.

### 5. Task loop (sequential - by design)

Repeat until no `[ ]` remain in any Task section:

1. `loop-state.py bump task_loop_iterations --scope 4` (exit 3 -> escalate)
2. Re-read the plan file; find the first Task section with remaining `[ ]`
3. Announce to the user: task title + unchecked items
4. Spawn **one** `Agent` subagent (`general-purpose`, `model: <executor>`) with the prompt from
   [references/task-prompt.md](references/task-prompt.md), filled per the context rules below
5. Wait for it to finish before starting the next
6. **Gate:** `python3 $L/verify-gate.py run --label 4`
7. Task done = its checkboxes are all `[x]` **and** the gate is green. Otherwise:
   - `loop-state.py bump task_retries --scope task-N` (exit 3 -> escalate per limits.md)
   - fresh subagent, same task, with `RETRY_NOTES` = what failed (unchecked items and/or the
     failing gate steps + their tails from `.llm/verify/last.json`) and what the previous
     attempt changed (`git diff --stat`). An identical prompt is not a retry.
   - Exception: the task's checkboxes say `(fails until Task M)` and only the tests that task
     introduced fail -> record `loop-state.py open add --step 4 --severity MINOR "red by design until Task M"`,
     continue; close it when Task M's gate is green.
8. One line to the user + `progress.md`: `Task N completed (gate green)` (or the failure)

**The orchestrator must not** implement, debug, or fix code itself. Retry with a fresh
subagent and pass the error details.

### Context rules for task subagents

From `~/.claude/skills/agentic-loop/references/context-discipline.md`:

- Every task gets a **fresh** subagent. Its prompt carries only: the plan path + this task's
  section, the plan's Constraints section, the `.llm/manifest.json` entries matching the task's
  Files block (by path or tags), project rule files by path, and retry notes.
- Never paste chat history, brainstorm/planning transcripts, other tasks' diffs, or full logs.
- The subagent returns at most ~15 lines; details go to `progress.md` and the plan checkboxes.

### 6. Step 4.5 - Verify gate (blocking)

When all task checkboxes are done: `loop-state.py step 4 done`, Stage report, then
`loop-state.py step 4.5 in_progress` and `python3 $L/verify-gate.py run --label 4.5`.

- Green -> `loop-state.py step 4.5 done`, Stage report, go to reviews.
- Red -> repair loop from `~/.claude/skills/agentic-loop/references/verify-gate.md`:
  `bump verify_repairs --scope 4.5` -> `agentic-loop-fixer` with the failing tails as `G1…Gn`
  -> re-run the gate. Exit 3 from `bump` -> escalate. **Step 5 never starts on red.**

### 7. Reviews

Read and follow `~/.claude/skills/agentic-loop-review/SKILL.md` (phases 5-8, the gate after
every fixer run).

### 8. Completion

- Collect `[decision]` / `[deviation]` lines from `progress.md`; show them to the user
- Ask whether to run `agentic-loop-docs-pr` next
- Do **not** push; do **not** move the plan to `completed/` until reviews finish and the user
  agrees (or docs-pr does it)

## Why sequential

Plan tasks run one at a time on purpose. Coding tasks share files and the build, so parallel
implementers mostly create conflicts and duplicated work at several times the token cost;
parallel fan-out is reserved for independent, read-only work (the step 5 reviewers).

## Hard rules

- One task subagent at a time
- Plan file is the source of truth — always re-read
- The gate result is the orchestrator's `verify-gate.py`, never a subagent's "tests pass"
- Never delete, skip or weaken tests, lint rules or `.llm/verify.json` to get green
- Never dismiss review findings as "pre-existing" — pass full findings to the fixer
- Subagents must not ask the user questions; they log `[decision]` / `[deviation]` instead
- No commits unless the user opted in

## Telemetry

After each completed plan task, after step 4.5, and after the review handoff, emit a Stage
report: `~/.claude/skills/agentic-loop/references/stage-report.md`.
