# Verify gate (deterministic, blocking)

Four LLM review passes do not replace one green `build + lint + test`. Compilers, linters and
test runners are objective and cheap; LLM reviewers are subjective and expensive. The gate runs
the deterministic checks, writes machine-readable results, and **nothing downstream starts on
red**: reviews (5–8) never run on a red or stale tree, and no PR is opened from one.

Only the orchestrator's gate run counts. A subagent saying "tests pass" is not a gate result.

## Commands

```bash
G=~/.claude/agentic-loop/bin/verify-gate.py
python3 $G init              # detect commands -> .llm/verify.json (then confirm with the user)
python3 $G run --label 4.5   # run; exit 0 green, 1 red, 2 not configured
python3 $G check             # exit 0 only if the last full run is green AND the code is unchanged since
python3 $G show              # config in effect (or what detection would produce)
```

`run` prints one JSON object (`status`, `failed`, per-step `status`/`reason`/`log`) and writes
`.llm/verify/last.json` (with the last 60 lines of every failing step) plus full logs in
`.llm/verify/<step>.log`. It also updates `.llm/loop-state.json` (`verify`, `gates["verify@<label>"]`)
and appends a `verify` event to the telemetry ledger.

`check` compares a fingerprint of `HEAD` + working-tree diff + untracked files (excluding `.llm/`,
`docs/agentic/`, `docs/plans/`), so a green run goes stale as soon as code changes. Stale = red.
Outside a git repo the fingerprint is a path/size/mtime walk of the tree (same exclusions).

## Config: `.llm/verify.json` (committed)

```json
{
  "schema": 1,
  "timeout_s": 900,
  "fingerprint_exclude": [".llm", "docs/agentic", "docs/plans"],
  "steps": [
    {"name": "build", "cmd": "go build ./...", "blocking": true},
    {"name": "vet",   "cmd": "go vet ./..."},
    {"name": "lint",  "cmd": "golangci-lint run", "requires": "golangci-lint", "optional": true},
    {"name": "test",  "cmd": "go test ./...", "timeout": 1800}
  ]
}
```

- `blocking`: when this step fails, later steps are reported `not_run` (tests on a broken build are noise).
- `requires` + `optional`: a missing tool makes the step `skipped` instead of `fail`. Without
  `optional`, a missing tool is a failure.
- Detection covers Go, Rust, Node (package.json scripts), Python and Makefile `build`/`lint`/`test`
  targets. It is a starting point: cross-check it with CLAUDE.md / AGENTS.md / Makefile / CI config
  and **confirm with the user** before the first run. Commit it with the manifest (when the user commits).

## Where it runs

| When | Label | Red means |
|------|-------|-----------|
| Step 0 baseline | `0` | the default branch is already broken -> user gate (below) |
| After each plan task (step 4) | `4` | retry the task with the gate output (see plan-exec) |
| **Step 4.5** | `4.5` | repair loop; step 5 does not start |
| After every fixer run in steps 5–8 | `5`…`8` | repair loop; the next phase does not start |
| Before push (step 9) | `9` | repair loop; no push, no PR |

## Red -> repair loop

1. `loop-state.py bump verify_repairs --scope <label>` - exit 3 -> escalate ([limits.md](limits.md)).
2. Spawn `agentic-loop-fixer` with: the failing step names, the path `.llm/verify/last.json`, and
   the failing tails verbatim, framed as findings `G1`, `G2`, … Instructions: fix the cause; never
   delete, skip or weaken tests or lint rules to get green (no skip markers, no `nolint`/`noqa`/
   `eslint-disable`, no loosened assertions, no edits to `.llm/verify.json`).
3. `verify-gate.py run --label <label>`.
4. Green -> continue. Red -> back to 1.

The diff of a repair is checked by the next gate run; review phases see it as part of the branch diff.

## Red baseline (step 0)

If the baseline run is red, the default branch is already broken and step 4.5 would never pass.
Ask the user:

- **Fix first** - add a task for it at the top of the plan.
- **Narrow the gate** - edit `.llm/verify.json` (e.g. exclude a known-broken package), with the
  user's consent, and log a `[deviation]` in `progress.md`. The gate has no "known red" mode: it is
  always pass/fail on exactly what `verify.json` says.
- **Stop.**

## Unconfigured

`run` exits 2 when `.llm/verify.json` has no steps (nothing detected). Ask the user for the build/
test commands and write them into `verify.json`. A project with genuinely nothing to run (docs-only
repo) records `loop-state.py gate verify@4.5 skipped --note "no build/test commands: <user's words>"`.
