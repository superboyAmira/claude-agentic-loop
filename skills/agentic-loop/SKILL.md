---
name: agentic-loop
description: >-
  Full agentic work loop for Claude Code: step -1 markup bootstrap -> index ->
  brainstorm -> plan-make -> plan review -> plan-exec -> multi-phase review ->
  docs-pr -> human handoff. Use when the user says agentic-loop, /agentic-loop,
  run the loop, agentic cycle, or wants the full workflow.
---

# Agentic Loop

End-to-end workflow for Claude Code. Port of
[superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop),
itself inspired by [umputun/cc-thingz](https://github.com/umputun/cc-thingz).

```text
-1 Markup bootstrap (if needed)
-> 0 Index -> 1 Brainstorm -> 2 Plan Make -> 3 Plan Review -> 4 Plan Exec
-> 5 Agent Review -> 6 Code Smells -> 7 External Review -> 8 Critical Review
-> 9 Docs & PR -> 10 Human Review
```

## Required reading

1. [references/model-routing.md](references/model-routing.md)
2. [references/stage-report.md](references/stage-report.md) — **after every step**
3. [references/telemetry-hooks.md](references/telemetry-hooks.md) — real tokens/wall/subagents from the transcript ledger
4. [references/session-docs.md](references/session-docs.md) — brainstorm/planning -> structured docs
5. [references/step-minus-one.md](references/step-minus-one.md) — missing manifest / markup

**Summary — models** (Claude Code cannot switch the *parent* model; subagents pin their own via frontmatter):

- **-1**: `sonnet` subagent (fast markup bootstrap)
- **0-2** parent: **Opus** — ask the user to run `/model opus` before deep design
- **3** plan review: `agentic-loop-plan-review` subagent (`opus`)
- **4-6, 8-10**: `sonnet` subagents
- **7**: `agentic-loop-external-review` subagent (`opus`, independent-reviewer framing — see caveat in model-routing.md)

## How to run

You are the **orchestrator**. Read each skill and follow it. After every step, emit a Stage report.

| Step | Name | Skill / action | Model |
|------|------|----------------|-------|
| -1 | Markup bootstrap | [step-minus-one.md](references/step-minus-one.md) if no `.llm/manifest.json` | `sonnet` subagent |
| 0 | Index | Below | Parent (prefer Opus) |
| 1 | Brainstorm | `agentic-loop-brainstorm` skill | Parent Opus -> write `docs/agentic/...` |
| 2 | Plan Make | `agentic-loop-plan-make` skill | Parent Opus -> plan + session docs |
| 3 | Plan Review | `Agent` tool -> `agentic-loop-plan-review` | `opus` (pinned in agent) |
| 4 | Plan Exec | `agentic-loop-plan-exec` skill | `sonnet` subagents |
| 5-8 | Reviews | `agentic-loop-review` skill | `sonnet` + `opus` external |
| 9 | Docs & PR | `agentic-loop-docs-pr` skill | `sonnet`; promote needs-documenting |
| 10 | Human Review | Stop; hand off | — |

**Entry shortcuts** (argument to `/agentic-loop`):

- `full` — -1 -> 10 (enforce gates)
- `from-plan` — skip -1..3; start at 4
- `review-only` — 5 -> 8
- `pr-only` — 9 -> 10

Announce step number/name on every advance. **After every step** (and when pausing mid-step for
user gates), print a **Stage report** in chat and append it to
`docs/agentic/<session>/telemetry.md` — see [references/stage-report.md](references/stage-report.md).
Skipping telemetry is a process failure.

Example:

```markdown
### Stage report — Step 1 · Brainstorm
- status: in progress
- model_parent: claude-opus-5
- models_subagents: []
- agents_used: []
- tools: Read/Write/Bash
- files_touched: 3 (docs/agentic/20260910-iron-reputation-calendar/*)
- tokens: <from ledger or n/a>
- context: n/a
- wall_time: n/a
- cost_notes: markdown-only session docs
- artifacts: docs/agentic/20260910-iron-reputation-calendar/{README,brainstorm,needs-documenting}.md
- next: continue Q&A -> design -> plan-make
```

**Get real numbers from the transcript ledger instead of `n/a`** — see
[references/telemetry-hooks.md](references/telemetry-hooks.md). The collector is installed
user-wide by `install.sh` and wired into `~/.claude/settings.json`. At Step 0, check it is
firing (`telemetry-report.py status`), otherwise offer to run `install.sh`.

```bash
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py mark "Step N · Name"    # step start
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py report --step N --name "Name"   # step end
```

After the last completed step, print a **Loop cost summary** (wall + tokens + subagent counts)
per `references/stage-report.md` (`telemetry-report.py summary`). Persist to
`docs/agentic/<session>/telemetry.md`.

## Manifest + gitignore (mandatory)

Project agent state lives in **`.llm/`**, and `.llm/manifest.json` is the only part of it that is committed:

| Path | Committed | What |
|------|-----------|------|
| `.llm/manifest.json` | yes | navigation index |
| `.llm/telemetry/` | no | transcript ledger (`events.jsonl`, `session.json`) |
| `.claude/settings.local.json` | no | local Claude Code config |

The project `.gitignore` must contain `.llm/telemetry/` — never `.llm/` as a whole.

`.llm/manifest.json` may list **only git-trackable paths** (`git check-ignore` must be empty for each `documents[].path`).

- Do **not** index ignored session scratch (`docs/agentic/…` if ignored).
- If a **business / runbook** doc created in the loop is ignored: **un-ignore** it (prefer
  `/docs/*` + `!/docs/business/**`, not `/docs/`), then add it to the manifest. Details:
  [references/step-minus-one.md](references/step-minus-one.md).

## Step -1 — Markup bootstrap

Follow [step-minus-one.md](references/step-minus-one.md).
If `.llm/manifest.json` (or equivalent project markup: `CLAUDE.md`, `AGENTS.md`) is missing ->
create `.llm/` and the manifest via a `sonnet` subagent, add the gitignore entries, Stage
report, then continue.

## Step 0 — Index + model gate

1. **Parent model gate for planning (steps 0-2):** if a full cycle is planned
   (brainstorm / plan-make), the parent model should be **Opus**. If the picker is on
   Sonnet/Haiku, ask the user to run `/model opus` before deep design. Claude Code cannot
   switch the parent itself. Exceptions: explicit shortcuts like `skip model gate`,
   `from-plan`, `review-only`.
2. Read `.llm/manifest.json` -> `CLAUDE.md` -> `AGENTS.md` -> `README.md`.
3. Note language, test command, key packages, relevant business docs.
4. `git status -sb` + `git log --oneline -5`.
5. 5-10 line index summary -> Stage report -> step 1 (or skip brainstorm).

## Documentation mandate

Brainstorm + planning dialogue **must** be written to structured files under
`docs/agentic/yyyymmdd-<slug>/` (see session-docs.md). Chat-only outcomes are incomplete.
Maintain `needs-documenting.md` for extra docs debt; step 9 clears or files tickets.

## Gates (must ask)

- After brainstorm: Write plan / Start small / Stop (session docs already written)
- After plan-make: Auto review / Revise / Implement / Stop
- Before plan-exec: plan path + commit-per-task (default: no commits)
- After reviews: Docs & PR / Stop
- Before push/PR: explicit confirmation

## Autonomy rules

- Subagents implement/fix; orchestrator coordinates
- Prefer the pinned `agentic-loop-*` subagents (via the `Agent` tool, `subagent_type`)
- No force-push, no merge, no silent red tests
- Commits/push only with user consent

## Related

- Skills: `agentic-loop-*` under `~/.claude/skills/`
- Agents: `agentic-loop-*` under `~/.claude/agents/`
