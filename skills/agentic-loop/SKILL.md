---
name: agentic-loop
description: >-
  Full agentic work loop for Claude Code: step -1 markup bootstrap -> index ->
  brainstorm -> plan-make -> plan review -> plan-exec -> deterministic verify
  gate -> multi-phase review -> docs-pr -> human handoff. Resumable from
  .llm/loop-state.json. Use when the user says agentic-loop, /agentic-loop,
  run the loop, agentic cycle, resume the loop, or wants the full workflow.
---

# Agentic Loop

End-to-end workflow for Claude Code. Port of
[superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop),
itself inspired by [umputun/cc-thingz](https://github.com/umputun/cc-thingz).

```text
-1 Markup bootstrap (if needed)
-> 0 Index -> 1 Brainstorm -> 2 Plan Make -> 3 Plan Review -> 4 Plan Exec
-> 4.5 Verify gate -> 5 Agent Review -> 6 Code Smells -> 7 External Review
-> 8 Critical Review -> 9 Docs & PR -> 10 Human Review
```

## Required reading

1. [references/model-routing.md](references/model-routing.md) - roles -> models (the only file that names models)
2. [references/limits.md](references/limits.md) - caps, termination conditions, escalation
3. [references/verify-gate.md](references/verify-gate.md) - deterministic build/lint/test gate
4. [references/loop-state.md](references/loop-state.md) - checkpoint + resume
5. [references/context-discipline.md](references/context-discipline.md) - fresh context per task, distilled returns
6. [references/stage-report.md](references/stage-report.md) - **after every step**
7. [references/telemetry-hooks.md](references/telemetry-hooks.md) - real tokens/wall/subagents from the transcript ledger
8. [references/session-docs.md](references/session-docs.md) - brainstorm/planning -> structured docs
9. [references/step-minus-one.md](references/step-minus-one.md) - missing manifest / markup

Tools (installed by `install.sh`; run from the project directory):

```bash
L=~/.claude/agentic-loop
python3 $L/bin/loop-state.py show                      # where the loop is, what is next
python3 $L/bin/verify-gate.py run --label 4.5          # deterministic gate, JSON out
python3 $L/hooks/telemetry-report.py mark "Step N · Name"
python3 $L/hooks/telemetry-report.py report --step N --name "Name"
```

## How to run

You are the **orchestrator**. Read each skill and follow it. Roles resolve to models in
model-routing.md (Claude Code cannot switch the *parent* model; subagents pin their own).

| Step | Name | Skill / action | Role |
|------|------|----------------|------|
| -1 | Markup bootstrap | [step-minus-one.md](references/step-minus-one.md) if no `.llm/manifest.json` | `cheap` subagent |
| 0 | Index | Below | parent (`planner` if steps 1-2 follow) |
| 1 | Brainstorm | `agentic-loop-brainstorm` skill | parent `planner` -> `docs/agentic/...` |
| 2 | Plan Make | `agentic-loop-plan-make` skill | parent `planner` -> plan + session docs |
| 3 | Plan Review | `Agent` tool -> `agentic-loop-plan-review` | `plan-reviewer` (pinned) |
| 4 | Plan Exec | `agentic-loop-plan-exec` skill | `executor` subagents, one task at a time |
| 4.5 | Verify gate | [verify-gate.md](references/verify-gate.md): `verify-gate.py run --label 4.5` + repair loop | no model |
| 5-8 | Reviews | `agentic-loop-review` skill | `reviewer` + `external-reviewer`; gate after every fixer |
| 9 | Docs & PR | `agentic-loop-docs-pr` skill | `cheap`; gate `check` before push |
| 10 | Human Review | Stop; hand off | — |

**Entry shortcuts** (argument to `/agentic-loop`):

- `full` — -1 -> 10 (enforce gates)
- `from-plan` — skip -1..3; start at 4
- `review-only` - 4.5 -> 8 (the gate runs first: reviews never start red)
- `pr-only` - 9 -> 10 (`verify-gate.py check` first)
- `resume` - continue from `.llm/loop-state.json` ([loop-state.md](references/loop-state.md))
- `eval <plan>` - non-interactive replay for the eval harness (below)

## Every step

1. `loop-state.py step N in_progress` and `telemetry-report.py mark "Step N · Name"`.
2. Announce the step number/name; do the step.
3. Check its termination condition ([limits.md](references/limits.md)). Before every capped
   attempt: `loop-state.py bump <counter> --scope <x>`; exit `3` -> escalate, do not retry.
4. `loop-state.py step N done`, then `telemetry-report.py report` -> fill the judgement fields ->
   **Stage report** in chat + append to `docs/agentic/<session>/telemetry.md`
   ([stage-report.md](references/stage-report.md)). Skipping it is a process failure.
5. Read the report's `context:` line; above `context_warn_tokens`, recommend `/compact` or a fresh
   session + `/agentic-loop resume` at this boundary ([context-discipline.md](references/context-discipline.md)).

Pausing for a user gate mid-step: `loop-state.py await "<question>"` and a Stage report with
`status: in progress`.

Example:

```markdown
### Stage report — Step 1 · Brainstorm
- status: in progress
- model_parent: <planner model id from the ledger>
- models_subagents: []
- agents_used: []
- tools: Read x6 / Write x3 / Bash x2
- files_touched: 3 (docs/agentic/20260910-iron-reputation-calendar/*)
- tokens: parent in 412,880 / out 6,114 over 9 message(s); total 418,994
- context: ~61k tokens in the last parent prompt (peak 61k)
- wall_time: 7m 12s
- cost_notes: markdown-only session docs
- artifacts: docs/agentic/20260910-iron-reputation-calendar/{README,brainstorm,needs-documenting}.md
- next: continue Q&A -> design -> plan-make
```

After the last completed step, print the **Loop cost summary** (`telemetry-report.py summary`)
and persist it to `docs/agentic/<session>/telemetry.md`.

## Manifest + gitignore (mandatory)

Project agent state lives in **`.llm/`**. Shared project knowledge is committed; runtime state is not:

| Path | Committed | What |
|------|-----------|------|
| `.llm/manifest.json` | yes | navigation index |
| `.llm/verify.json` | yes | verify gate commands |
| `.llm/loop-state.json` | no | loop checkpoint (resume) |
| `.llm/verify/` | no | gate results + logs |
| `.llm/telemetry/` | no | transcript ledger (`events.jsonl`, `session.json`) |
| `.claude/settings.local.json` | no | local Claude Code config |

The project `.gitignore` must list `.llm/telemetry/`, `.llm/verify/` and `.llm/loop-state.json` -
never `.llm/` as a whole. `.llm/manifest.json` may list **only git-trackable paths**
(`git check-ignore` must be empty for each `documents[].path`). Details, including how to
un-ignore business docs: [references/step-minus-one.md](references/step-minus-one.md).

## Step -1 — Markup bootstrap

Follow [step-minus-one.md](references/step-minus-one.md).
If `.llm/manifest.json` (or equivalent project markup: `CLAUDE.md`, `AGENTS.md`) is missing ->
create `.llm/`, the manifest and `.llm/verify.json` via a `cheap` subagent, add the gitignore
entries, Stage report, then continue.

## Step 0 - Index, state, model gate, baseline

1. **Existing loop?** If `.llm/loop-state.json` exists with status other than `done`: run
   `loop-state.py show` and ask **resume** / **start fresh** ([loop-state.md](references/loop-state.md)).
2. **Parent model gate for planning (steps 0-2):** if brainstorm / plan-make will run, the parent
   should be on the `planner` model. Otherwise ask the user to run `/model <planner>`; Claude Code
   cannot switch the parent itself. Exceptions: `skip model gate`, `from-plan`, `review-only`,
   `resume` past step 2, `eval`.
3. Read `.llm/manifest.json` -> `CLAUDE.md` -> `AGENTS.md` -> `README.md`.
4. Note language, key packages, relevant business docs.
5. **Verify config:** no `.llm/verify.json` -> `verify-gate.py init`, show the detected steps,
   cross-check with CLAUDE.md / Makefile / CI, confirm with the user.
6. **Baseline:** `verify-gate.py run --label 0`. Red -> user gate: fix first / narrow the gate /
   stop ([verify-gate.md](references/verify-gate.md)). Do not start implementation on an
   unexplained red baseline.
7. `git status -sb` + `git log --oneline -5`.
8. `loop-state.py init --session <yyyymmdd-slug> --entry <mode>` (slug from the task; `set` it
   later if brainstorm renames it).
9. 5-10 line index summary -> Stage report -> step 1 (or skip brainstorm).

## Step 4.5 - Verify gate

Blocking. `verify-gate.py run --label 4.5`; red -> repair loop (fixer with the failing tails,
`verify_repairs` cap 3, then escalate). Step 5 starts only when `verify-gate.py check` exits 0.
The same gate runs after every fixer in steps 5-8 and before push in step 9.

## Documentation mandate

Brainstorm + planning dialogue **must** be written to structured files under
`docs/agentic/yyyymmdd-<slug>/` (see session-docs.md). Chat-only outcomes are incomplete.
Maintain `needs-documenting.md` for extra docs debt; step 9 clears or files tickets.

## Gates (must ask)

- Step 0: resume / start fresh (existing state); red baseline: fix / narrow / stop
- After brainstorm: Write plan / Start small / Stop (session docs already written)
- After plan-make: Auto review / Revise / Implement / Stop
- Before plan-exec: plan path + commit-per-task (default: no commits)
- Any `LIMIT HIT` or `blocked` state: escalation options from limits.md
- A finding that needs a plan change: add `+` tasks / defer / stop
- After reviews: Docs & PR / Stop
- Before push/PR: explicit confirmation

## Autonomy rules

- Subagents implement/fix; the orchestrator coordinates and runs the gate
- Prefer the pinned `agentic-loop-*` subagents (via the `Agent` tool, `subagent_type`)
- No step 5-9 on a red or stale gate; the orchestrator's `verify-gate.py` result is the only
  "tests pass" that counts
- Never delete, skip or weaken tests, lint rules or `.llm/verify.json` to get green
- Caps come from limits.md and are enforced by `loop-state.py bump`; `LIMIT HIT` -> block and ask,
  never a silent extra attempt
- Reviews do not loop back to step 4 on their own (limits.md)
- No force-push, no merge; commits/push only with user consent

## Eval mode (`/agentic-loop eval <plan>`)

Non-interactive replay used by `bin/eval.py` (environment `AGENTIC_LOOP_EVAL=1`). Nobody is
there to answer, so:

- Entry = `from-plan` with `<plan>` on the current checkout (a detached worktree): no branch
  creation, no commits, no push, no PR; step 9 is skipped.
- Every "must ask" gate takes the forward default: implement, `commit_per_task=false`, run all
  review phases. Skip the model gate. Do not call AskUserQuestion.
- Missing `.llm/verify.json` -> `verify-gate.py init` and use the detection as-is.
- Red baseline, `LIMIT HIT`, or a finding that needs a plan change -> `loop-state.py block` and
  stop. That run counts as a failure in the results; that is the point.
- Still write loop state, telemetry marks, findings and Stage reports: they are the metrics.
- End with `loop-state.py done` when step 8 finishes.

Eval harness usage (record cases, run, compare versions): `python3 ~/.claude/agentic-loop/bin/eval.py --help`
and `evals/README.md` in the repo.

## Related

- Skills: `agentic-loop-*` under `~/.claude/skills/`
- Agents: `agentic-loop-*` under `~/.claude/agents/`
- Scripts: `~/.claude/agentic-loop/{bin,hooks}/`
