# Eval loop

Without evals you cannot answer "did the loop get better after I changed the reviewer prompt?".
The eval loop replays 10-20 real, recorded tasks under a label (a skill version or an
experiment), measures each run objectively, and compares labels on the cases they share.

Cases and results are **user-local** (`~/.claude/agentic-loop/evals/`), never committed here:
plans and repo paths come from private projects and this repo is public.

```bash
E=~/.claude/agentic-loop/bin/eval.py
```

## 1. Record cases from real loops

After a loop finishes in a project (plan in `docs/plans/completed/`), from that project:

```bash
python3 $E record --id achievements-iron-rep \
  --plan docs/plans/completed/20260910-iron-reputation.md \
  --acceptance "go test ./internal/service/achievements/..." \
  --notes "calendar edge cases; external review found the TZ bug"
```

- `--base` defaults to the merge-base of `HEAD` with the default branch: the code the loop
  started from. Pass it explicitly if the branch was rebased.
- `--acceptance` (repeatable) is a hidden check the loop never sees - e.g. the tests the human
  wrote or kept after review. It is the closest thing to ground truth; add one whenever you can.
- Aim for 10-20 cases that cover your usual work: small fixes, features, refactors, one or two
  that went badly.

`python3 $E list` shows what is recorded.

## 2. Run

```bash
python3 $E run --all --label v1.1.0
python3 $E run --case achievements-iron-rep --label reviewer-prompt-b --keep
```

Per case: a detached `git worktree` at the base commit (your checkout is untouched), the plan
copied into `docs/plans/`, then the runner - by default

```bash
claude -p "/agentic-loop eval docs/plans/<plan>.md" --output-format json \
  --permission-mode auto --permission-prompts none --max-budget-usd 20
```

with `AGENTIC_LOOP_EVAL=1` and the telemetry ledger pointed into the worktree. After the loop,
the harness runs its own checks: the verify gate, the case's acceptance commands, the loop state
and the telemetry summary. The worktree is removed unless `--keep`.

Override the runner, permission mode, budget or timeout in `~/.claude/agentic-loop/evals/config.json`:

```json
{"runner": "claude -p \"/agentic-loop eval {plan}\" --output-format json --permission-mode {permission_mode} --permission-prompts none --max-budget-usd {budget_usd}",
 "permission_mode": "auto", "budget_usd": 20, "timeout_s": 7200}
```

The loop runs project commands (build, tests) unattended. Run evals on your own repositories; use
`bypassPermissions` only inside a container or VM.

## 3. Read the results

```bash
python3 $E report                         # one row per label
python3 $E compare v1.1.0 reviewer-prompt-b   # only cases both labels ran
```

| Metric | Meaning |
|--------|---------|
| `verify_pass` | the harness's own gate run is green after the loop |
| `acceptance_pass` | the hidden acceptance commands pass |
| `finished` | the loop reached `done` instead of `blocked` (a cap or escalation) |
| `cost_usd` | `total_cost_usd` from the runner's JSON output |
| `tokens` | parent + subagent tokens from the telemetry ledger |
| `wall_s` | runner wall time |
| `finding_acceptance` | accepted / produced review findings (review yield) |
| `open_findings` | findings left open at the end |

Raw rows: `~/.claude/agentic-loop/evals/results.jsonl`; per-run artefacts (runner output, gate
result, telemetry summary, acceptance logs): `~/.claude/agentic-loop/evals/runs/`.

## How to use it

- Change one thing per label (a reviewer prompt, a cap, a role's model), run the same cases,
  `compare`. Two or three runs per case per label smooth out run-to-run variance.
- Pair it with `telemetry-report.py yield` from real work: yield tells you which reviewer looks
  weak; the eval tells you whether cutting it hurts `acceptance_pass`.
- Keep a regression set: when a real loop fails in a new way, record it as a case.
