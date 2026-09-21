# Limits and termination (agentic-loop)

The two most common failure modes of multi-agent systems are **step repetition** (repeating
work without progress) and **not knowing when to stop** (MAST taxonomy, Cemri et al. 2025:
15.7% and 12.4% of failures). The loop does not rely on the model remembering how many times
it tried: every repeatable action has a cap, and the cap is enforced by a script's exit code.

## Caps

This table is the single source of truth: `loop-state.py` parses it (rows of the form
`` | `key` | number | ``). Change a number here, not in the skills.

| Key | Cap | Counts | `--scope` | On hit |
|-----|-----|--------|-----------|--------|
| `plan_review_rounds` | 2 | step 3 `NEEDS REVISION` -> revise -> re-review rounds | `3` | escalate |
| `task_retries` | 1 | fresh-subagent retries of one plan task | `task-N` | escalate |
| `task_loop_iterations` | 50 | task subagents spawned in step 4 | `4` | escalate |
| `verify_repairs` | 3 | fixer runs spent turning a red gate green | gate label (`4`, `4.5`, `5`…`9`) | escalate |
| `review_iterations` | 5 | step 5 reviewers -> fixer cycles | `5` | stop cycling, record leftovers, continue |
| `external_iterations` | 5 | step 7 review -> fixer cycles | `7` | stop cycling, record leftovers, continue |
| `replan_cycles` | 1 | returns from reviews to step 4 for new `+` tasks | `loop` | escalate |
| `context_warn_tokens` | 150000 | parent prompt size, from the Stage report `context:` line (a threshold, not a counter) | - | recommend compaction or a fresh session + resume |

How to use a cap:

```bash
python3 ~/.claude/agentic-loop/bin/loop-state.py bump verify_repairs --scope 4.5
# exit 0: go ahead   |   exit 3: LIMIT HIT -> escalate (below), do not try again
```

Bump **before** the attempt it counts. A cap of 3 allows three attempts; the fourth bump exits 3.

## Termination conditions

| Step | Done when | Also ends when |
|------|-----------|----------------|
| -1 | manifest + `.llm/verify.json` written, `.gitignore` updated | - |
| 0 | index summary written, loop state initialised, baseline gate recorded | red baseline -> user gate |
| 1 | the user picks Write plan / Start now / Done, and `brainstorm.md` is written | user stops |
| 2 | plan file + `planning.md` written | user stops |
| 3 | plan review says `APPROVE`, or the user overrides | `plan_review_rounds` -> escalate |
| 4 | every plan checkbox is `[x]` **and** the gate after the last task is green | `task_retries` / `task_loop_iterations` -> escalate |
| 4.5 | `verify-gate.py check` exits 0 | `verify_repairs[4.5]` -> escalate |
| 5 | all five reviewers are clean, **or** an iteration where the fixer accepted 0 findings (no progress), **or** `review_iterations`; then the gate is green | `verify_repairs[5]` -> escalate |
| 6 | one smells pass (+ fixer if needed); gate green | `verify_repairs[6]` -> escalate |
| 7 | no CRITICAL/MAJOR left, **or** no progress, **or** `external_iterations`; gate green | `verify_repairs[7]` -> escalate |
| 8 | one critical-only pass (+ fixer if needed); gate green | `verify_repairs[8]` -> escalate |
| 9 | `verify-gate.py check` green and the PR is created, or the user stops | red gate -> repair loop, then escalate |
| 10 | handoff printed; the agent does nothing more unless asked | - |

## Anti-repetition rules

- **No progress = stop.** In steps 5 and 7, an iteration where the fixer fixed nothing (every
  finding rejected) ends that phase. More rounds of the same reviewers produce noise, not fixes.
- **Rejected findings are not re-sent.** Pass the previous iterations' rejected findings to the
  reviewers as "already rejected - do not re-raise without new evidence", and drop exact repeats
  before calling the fixer.
- **Retries must differ.** A task or repair retry carries a failure diagnosis (what failed, the
  gate output tail, what the previous attempt changed). Re-sending an identical prompt is not a
  retry.

## Reviews never loop back to step 4 on their own

Findings from steps 5–8 are fixed in place by the fixer. A finding that needs a **plan change**
(new task, design change, scope change) is not the fixer's job:

1. The fixer rejects it with `needs-plan-change: <why>`.
2. The orchestrator records it: `loop-state.py open add --step N --severity MAJOR "<summary>"`.
3. At the end of the step, ask the user: add `+` tasks to the plan and re-enter step 4 for those
   tasks only (`bump replan_cycles`), defer it to a follow-up, or stop.

## Escalation protocol (every "escalate" above)

1. `loop-state.py block "<counter/condition>: <one-line reason>"`, then a Stage report with
   `status: blocked`.
2. Tell the user what hit the cap, what was tried (attempt count, last gate failure tail or the
   leftover findings), and the options:
   - give guidance and allow more attempts -> `loop-state.py reset <counter> --scope X --reason "<user's words>"`
   - skip this gate -> `loop-state.py gate <name> skipped --note "<user's words>"` (only on an
     explicit instruction; steps 5-9 still refuse to start on a red gate unless the user says so for that step)
   - stop -> leave the state `blocked`; `/agentic-loop resume` picks it up later.
3. Never continue past `blocked` without an explicit answer. No silent "one more try".

In eval mode (`/agentic-loop eval`) there is nobody to ask: block and stop. That run counts as a
failure in the eval results, which is the point.
