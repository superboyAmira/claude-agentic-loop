# Changelog

## 1.1.0 - 2026-09-21

Reliability pass driven by a review of the loop against the multi-agent failure research
(MAST taxonomy, Anthropic's context-engineering and long-running-harness write-ups).

- **Deterministic verify gate** (`bin/verify-gate.py`, new step 4.5): runs the project's
  build / vet / lint / test commands from `.llm/verify.json`, writes machine-readable results to
  `.llm/verify/last.json`, and blocks every review phase and the PR on a red or stale tree.
  Runs after each plan task and after every fixer; red -> fixer repair loop (max 3), then escalate.
- **Caps and termination conditions** (`references/limits.md`, parsed by `bin/loop-state.py`):
  plan-review rounds, task retries, gate repairs, review iterations, replans. `loop-state.py bump`
  exits 3 on a hit; explicit "done when" per step; no-progress stop for review loops; reviews never
  loop back to plan-exec without the user.
- **Resumable state** (`.llm/loop-state.json` via `bin/loop-state.py`) and `/agentic-loop resume`.
  The plan-exec progress log moved from `/tmp` to `docs/agentic/<session>/progress.md`.
- **Model roles**: skills, agents and README refer to roles (`planner`, `plan-reviewer`,
  `executor`, `reviewer`, `external-reviewer`, `cheap`); `model-routing.md` is the only file that
  names models. `bin/check-models.py` regenerates agent `model:` lines and fails on drift
  (install warns, release refuses).
- **Review yield telemetry**: finding IDs per reviewer, fixer answers per ID,
  `telemetry-report.py findings` per reviewer invocation, `telemetry-report.py yield` across all
  runs and projects.
- **Context discipline** (`references/context-discipline.md`): fresh subagent per task with only
  its plan section, Constraints and matching manifest entries; distilled returns; Constraints
  section in the plan template; the Stage report `context:` line is now the parent's real prompt
  size, with a warning threshold.
- **Eval loop** (`bin/eval.py`, `evals/README.md`, `/agentic-loop eval <plan>`): record real tasks,
  replay them in throwaway worktrees, measure gate pass / hidden acceptance / finished / yield /
  tokens / cost, compare labels. Cases and results stay in `~/.claude/agentic-loop/evals/`.
- **Telemetry fixes**: token totals were over-counted 2-3x (the transcript repeats a message's
  usage on every content-block row; now collapsed per message id); subagent tokens are now
  counted from `<session>/subagents/`; loops spanning several sessions are summed across every
  transcript the hooks saw; `<synthetic>` messages no longer become `model_parent`.
- **Fixes**: `install.sh --uninstall` no longer deletes `~/.claude/agentic-loop/{telemetry,evals}`;
  docs no longer tell you to run `install.sh` from `~/.claude/agentic-loop` (it is not installed there).
- README: sequential plan execution documented as a design decision.

## 1.0.0 — 2026-09-11

- Initial Claude Code port of [superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop):
  6 skills, 8 pinned-model subagents, transcript-based telemetry hooks.
- `install.sh` — installs into `~/.claude/{skills,agents,agentic-loop/hooks}` and wires
  telemetry hooks into `~/.claude/settings.json`. Also supports `--no-hooks` and `--uninstall`.
- `sync-from-local.sh` — pulls edits made to the installed copy back into this repo.
- `release.sh` — version/changelog/tag helper for publishing new versions.
