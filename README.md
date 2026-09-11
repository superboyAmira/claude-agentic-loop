# claude-agentic-loop

A Claude Code port of [superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop):
an end-to-end agentic work loop delivered as **skills + pinned-model subagents + telemetry
hooks**, so you just run `/agentic-loop` and everything wires itself up.

```text
-1 Markup bootstrap -> 0 Index -> 1 Brainstorm -> 2 Plan Make -> 3 Plan Review
-> 4 Plan Exec -> 5 Agent Review -> 6 Code Smells -> 7 External Review
-> 8 Critical Review -> 9 Docs & PR -> 10 Human Review
```

## Install (client machine)

```bash
git clone https://github.com/superboyAmira/claude-agentic-loop.git
cd claude-agentic-loop
chmod +x install.sh
./install.sh                 # skills + agents + telemetry hooks
./install.sh --no-hooks      # skip telemetry
./install.sh --uninstall     # remove everything
```

`install.sh` copies:

| From | To |
|------|----|
| `skills/agentic-loop*` | `~/.claude/skills/` |
| `agents/agentic-loop-*.md` | `~/.claude/agents/` |
| `hooks/*` | `~/.claude/agentic-loop/hooks/` |

and merges 5 hook entries (`SessionStart`, `Stop`, `SubagentStop`, `PreCompact`,
`SessionEnd`) into `~/.claude/settings.json` (idempotent, existing hooks preserved,
timestamped backup written).

Restart Claude Code so it picks up the new skills.

## Use

| Command | Does |
|---------|------|
| `/agentic-loop` | the whole loop, with user gates |
| `/agentic-loop full` | same, explicit |
| `/agentic-loop from-plan` | skip -1..3, start at Plan Exec |
| `/agentic-loop review-only` | just steps 5-8 |
| `/agentic-loop pr-only` | just Docs & PR |
| `/agentic-loop-brainstorm` | step 1 standalone |
| `/agentic-loop-plan-make` | step 2 standalone |
| `/agentic-loop-plan-exec` | step 4 standalone |
| `/agentic-loop-review` | steps 5-8 standalone |
| `/agentic-loop-docs-pr` | step 9 standalone |

The `agentic-loop` skill is the **orchestrator**: it reads each sub-skill, runs the
pinned subagents via the `Agent` tool, enforces the gates, and emits a Stage report
after every step.

## Subagents (`~/.claude/agents/`)

| Agent | Model | Role |
|-------|-------|------|
| `agentic-loop-plan-review` | opus | step 3 — plan quality gate |
| `agentic-loop-quality` | sonnet | review — best practices |
| `agentic-loop-implementation` | sonnet | review — conformance to plan |
| `agentic-loop-testing` | sonnet | review — coverage / edge cases |
| `agentic-loop-documentation` | sonnet | review — comments / docstrings |
| `agentic-loop-simplification` | sonnet | review — redundancy / YAGNI |
| `agentic-loop-fixer` | sonnet | applies confirmed findings |
| `agentic-loop-external-review` | opus | step 7 — adversarial fresh-context pass |

## Differences from the Cursor original

| Cursor | Here |
|--------|------|
| `.cursor/skills/`, `.cursor/agents/` | `~/.claude/skills/`, `~/.claude/agents/` |
| `Task` tool with `model:` slugs (Grok / Sol / Gemini) | `Agent` tool, `model:` = `opus`/`sonnet`/`haiku` |
| Parent model gate on Opus 5 1M / GPT-5.6 Sol 1M | Parent gate asks you to run `/model opus` |
| Step 7 external review = Gemini (different family) | Step 7 = `opus`, fresh adversarial context (not cross-family — see `skills/agentic-loop/references/model-routing.md`) |
| Cursor hooks expose per-turn tokens | Telemetry reads `message.usage` from the session transcript JSONL |
| `~/.cursor/hooks.json` | `~/.claude/settings.json` `hooks` block |
| `.cursor/skills/.../*.md` uses repo-relative paths, rewritten on install/sync | Every reference is already the absolute `~/.claude/...` path — no rewriting needed either direction |

Everything else — the 11 stages, the gates, the session-docs mandate
(`docs/agentic/yyyymmdd-<slug>/`), the `.llm/manifest.json` + `.gitignore` rules, the
Stage-report-after-every-step discipline, the 5-parallel-reviewers-then-fixer loop
(max 5 iterations) — is carried over as-is.

## Telemetry

```bash
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py status
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py mark   "Step 4 · Plan Exec"
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py report --step 4 --name "Plan Exec"
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py summary
```

The `SessionStart` hook records the live transcript path in
`<project>/.llm/telemetry/session.json`; the reporter sums `message.usage` between
marks. Context-window usage is not exposed to skills in Claude Code, so that field is
always `n/a`. Subagent token usage is not attributed to the parent transcript — the
reporter reports subagent cost as duration + tool-call counts.

Ledger location: `<project>/.llm/telemetry/` when `.llm/` exists, else
`~/.claude/agentic-loop/telemetry/<project>-<hash>/`, overridable with
`$CLAUDE_LOOP_TELEMETRY_DIR`. Never committed (`.gitignore` + a self-ignoring
`.gitignore` in the dir).

## Publishing a new version (maintainer workflow)

Two scripts cover the round trip between this repo and your local `~/.claude`:

```bash
# 1. You edited an installed skill/agent directly in ~/.claude while testing it.
#    Pull those edits back into the repo (stages them, shows a diff, doesn't push):
./sync-from-local.sh
./sync-from-local.sh --commit "tune plan-exec retry wording"
./sync-from-local.sh --commit "..." --push

# 2. Cut a release: bump VERSION, prepend a CHANGELOG entry, commit + tag.
./release.sh patch            # 1.0.0 -> 1.0.1
./release.sh minor --push     # 1.0.1 -> 1.1.0, and push commit + tag
./release.sh 2.0.0            # set an explicit version
```

`sync-from-local.sh` never pushes unless you pass `--push`. `release.sh` never pushes
unless you pass `--push`. Neither force-pushes or touches anything outside
`skills/`, `agents/`, `hooks/`, `VERSION`, `CHANGELOG.md`.

Client machines stay on `install.sh` — they never need these two scripts.

## Layout

```
claude-agentic-loop/
├── install.sh              # client: repo -> ~/.claude
├── sync-from-local.sh      # maintainer: ~/.claude -> repo
├── release.sh              # maintainer: version + changelog + tag
├── VERSION
├── CHANGELOG.md
├── README.md
├── LICENSE
├── skills/
│   ├── agentic-loop/SKILL.md + references/{model-routing,stage-report,session-docs,step-minus-one,telemetry-hooks}.md
│   ├── agentic-loop-brainstorm/SKILL.md
│   ├── agentic-loop-plan-make/SKILL.md + references/plan-template.md
│   ├── agentic-loop-plan-exec/SKILL.md + references/task-prompt.md
│   ├── agentic-loop-review/SKILL.md + references/{reviewers,fixer}.md
│   └── agentic-loop-docs-pr/SKILL.md
├── agents/agentic-loop-*.md          (8 subagents)
└── hooks/
    ├── telemetry-collect.sh / .py    (hook entrypoint)
    ├── telemetry-report.py           (mark / report / summary / status)
    ├── merge-hooks.py                (settings.json wiring, --uninstall)
    ├── _ledger.py                    (shared ledger-path logic)
    └── hooks.template.json
```

## Credit

Workflow design, stage structure, prompts, and telemetry approach ported from
[superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop),
inspired by [umputun/cc-thingz](https://github.com/umputun/cc-thingz).
