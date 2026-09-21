# Loop state and resume

A session can die at step 6. `.llm/loop-state.json` is the checkpoint that lets the next session
continue instead of starting over. It is **JSON, not Markdown** (models are far less likely to
rewrite a JSON record inappropriately), and nobody edits it by hand: every change goes through
`loop-state.py`, which writes atomically and enforces the caps from [limits.md](limits.md).

The file is runtime state: gitignored, never committed.

```bash
S=~/.claude/agentic-loop/bin/loop-state.py
python3 $S show            # human summary + next step (this is the resume entry point)
python3 $S show --json     # raw state
```

## Schema (abridged)

```json
{
  "schema": 1,
  "session": "20260921-iron-reputation",
  "session_dir": "docs/agentic/20260921-iron-reputation",
  "plan": "docs/plans/20260921-iron-reputation.md",
  "branch": "iron-reputation",
  "entry": "full",
  "status": "in_progress | awaiting_user | blocked | done",
  "current_step": "6",
  "steps": {"0": {"status": "done", "at": "..."}, "6": {"status": "in_progress", "at": "..."}},
  "gates": {"plan-review": {"status": "pass"}, "verify@4.5": {"status": "pass"}},
  "gates_passed": ["plan-review", "verify@4.5"],
  "verify": {"status": "pass", "at": "...", "fingerprint": "…", "failed": []},
  "counters": {"verify_repairs": {"4.5": 1}, "review_iterations": {"5": 2}},
  "limits": {"verify_repairs": 3, "...": 0},
  "open_findings": [{"n": 1, "step": "7", "severity": "MAJOR", "summary": "...", "status": "open"}],
  "blocked_reason": null
}
```

`verify` and `gates["verify@<label>"]` are written by `verify-gate.py run`; everything else by
`loop-state.py`. `limits` is a snapshot taken at `init`, so a resumed loop keeps its original caps.

## When to write

| Moment | Command |
|--------|---------|
| Step 0, new loop (slug from the task) | `loop-state.py init --session <yyyymmdd-slug> --entry <full\|from-plan\|…>` |
| Plan / branch known | `loop-state.py set --plan docs/plans/<file>.md --branch <b>` |
| Every step start | `loop-state.py step N in_progress` |
| Every step end (before the Stage report) | `loop-state.py step N done` (or `skipped`) |
| Plan review verdict | `loop-state.py gate plan-review pass\|fail` |
| Before every capped attempt | `loop-state.py bump <counter> --scope <x>` (exit 3 -> escalate) |
| User gate reached | `loop-state.py await "<question>"` |
| Escalation | `loop-state.py block "<reason>"` |
| Leftover / deferred finding | `loop-state.py open add --step N --severity S "<summary>"` |
| After step 10 | `loop-state.py done` |

Task-level progress is **not** duplicated here: the plan's checkboxes are the truth for tasks,
`docs/agentic/<session>/progress.md` holds `[decision]` / `[deviation]` lines.

## Resume

Any `/agentic-loop` invocation first checks for `.llm/loop-state.json`. If it exists and its
status is not `done`, ask: **resume** / **start fresh** (`init --force` archives the old state as
`.llm/loop-state.<timestamp>.json`). `/agentic-loop resume` skips the question.

Resume procedure:

1. `loop-state.py show` -> session, plan, branch, next step, counters, open findings, gate freshness.
2. Branch check: if the checked-out branch differs from the state's, ask before doing anything.
3. Reload context from files, not memory: the plan file, `docs/agentic/<session>/progress.md`,
   the last Stage report in `telemetry.md`, `open_findings`.
4. Status `blocked` -> show `blocked_reason` and ask the user (escalation options in limits.md).
   Status `awaiting_user` -> re-ask the pending question.
5. Next step is 5 or later -> `verify-gate.py check`; stale or red -> run the gate with the next
   step's label and the repair loop before continuing.
6. `telemetry-report.py mark "Step N · <Name> (resumed)"`, then continue at step N.

Resuming in a **fresh session** is also the recommended way to shed context: the checkpoint
carries everything the next session needs (see [context-discipline.md](context-discipline.md)).
