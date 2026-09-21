# claude-agentic-loop

A Claude Code port of [superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop):
an end-to-end agentic work loop delivered as **skills + pinned-model subagents + a
deterministic verify gate + telemetry hooks**, so you just run `/agentic-loop` and everything
wires itself up.

```text
-1 Markup bootstrap -> 0 Index -> 1 Brainstorm -> 2 Plan Make -> 3 Plan Review
-> 4 Plan Exec -> 4.5 Verify gate -> 5 Agent Review -> 6 Code Smells
-> 7 External Review -> 8 Critical Review -> 9 Docs & PR -> 10 Human Review
```

## Install (client machine)

```bash
git clone https://github.com/superboyAmira/claude-agentic-loop.git
cd claude-agentic-loop
chmod +x install.sh
./install.sh                 # skills + agents + scripts + telemetry hooks
./install.sh --no-hooks      # skip telemetry wiring
./install.sh --uninstall     # remove everything
```

`install.sh` copies:

| From | To |
|------|----|
| `skills/agentic-loop*` | `~/.claude/skills/` |
| `agents/agentic-loop-*.md` | `~/.claude/agents/` |
| `hooks/*` | `~/.claude/agentic-loop/hooks/` |
| `bin/*` | `~/.claude/agentic-loop/bin/` |

and merges 5 hook entries (`SessionStart`, `Stop`, `SubagentStop`, `PreCompact`,
`SessionEnd`) into `~/.claude/settings.json` (idempotent, existing hooks preserved,
timestamped backup written). Scripts need `python3` (3.8+) and `git`.

Restart Claude Code so it picks up the new skills.

## Use

| Command | Does |
|---------|------|
| `/agentic-loop` | the whole loop, with user gates |
| `/agentic-loop full` | same, explicit |
| `/agentic-loop from-plan` | skip -1..3, start at Plan Exec |
| `/agentic-loop review-only` | verify gate, then steps 5-8 |
| `/agentic-loop pr-only` | gate check, then Docs & PR |
| `/agentic-loop resume` | continue from `.llm/loop-state.json` |
| `/agentic-loop eval <plan>` | non-interactive replay (used by the eval harness) |
| `/agentic-loop-brainstorm` | step 1 standalone |
| `/agentic-loop-plan-make` | step 2 standalone |
| `/agentic-loop-plan-exec` | steps 4-4.5 standalone |
| `/agentic-loop-review` | steps 5-8 standalone |
| `/agentic-loop-docs-pr` | step 9 standalone |

The `agentic-loop` skill is the **orchestrator**: it reads each sub-skill, runs the
pinned subagents via the `Agent` tool, runs the verify gate, enforces the gates and caps, keeps
the checkpoint, and emits a Stage report after every step.

## What keeps the loop honest

### Deterministic verify gate (step 4.5, and after every fixer)

LLM reviewers are subjective and expensive; the compiler, linter and tests are objective and
cheap. `bin/verify-gate.py` runs the project's build / vet / lint / test commands from
`.llm/verify.json` (detected at Step 0, confirmed by you, committed), writes machine-readable
results to `.llm/verify/last.json`, and exits non-zero on red. Step 5 never starts on red;
neither does any later review phase or the PR. A green run goes stale as soon as code changes
(tree fingerprint), and only the orchestrator's gate run counts - a subagent saying "tests pass"
does not. Red -> fixer with the failing output -> re-run, at most 3 times, then it asks you.

### Caps and termination conditions

Step repetition and not knowing when to stop are the two most common multi-agent failure modes.
Every repeatable action has a cap in
[`limits.md`](skills/agentic-loop/references/limits.md) (task retries, gate repairs, review
iterations, plan-review rounds, replans), enforced by `loop-state.py bump`, which exits `3` when a
cap is exceeded. A review phase also stops early when an iteration's fixer accepts nothing. Every
step has an explicit "done when"; reviews never loop back to plan-exec without asking you.

### Resumable state

`.llm/loop-state.json` (JSON, gitignored, written only through `bin/loop-state.py`) records the
session, plan, branch, current step, gates passed, counters and open findings. A session that
dies at step 6 continues with `/agentic-loop resume`, in the same or a fresh session.

### Context discipline

Every plan task runs in a fresh subagent that gets only the plan, its own task section, the
plan's Constraints and the matching manifest entries. Subagents return short summaries, raw
material stays in files, and the Stage report shows the parent's prompt size so you know when to
`/compact` or resume in a fresh session.

### Review yield telemetry

Every reviewer invocation records findings produced vs findings the fixer accepted
(`telemetry-report.py findings`), into a user-wide log. After 15-20 loops,
`telemetry-report.py yield` shows which review pass earns its cost and which produces 2 accepted
findings out of 40 - so it can be cut or re-prompted on data, not intuition.

### Eval loop

`bin/eval.py` replays recorded real tasks (`record` after a loop, `run` in a throwaway git
worktree at the original base commit, `report` / `compare` across labels) and measures verify
gate pass rate, hidden acceptance checks, finished-vs-blocked, review yield, tokens and cost.
Prompt or routing changes become measurable instead of guesswork. See [`evals/README.md`](evals/README.md).

## Design decision: sequential execution

Plan tasks run **one at a time**, and there is no "team of implementer agents". That is a
choice, not an omission. Coding tasks share files and the build, so parallel implementers mostly
produce conflicts and duplicated work at several times the token cost; Anthropic's own
multi-agent write-up notes that most coding tasks have far fewer truly parallelizable parts than
research. Parallelism is used only where work is independent and read-only: the five review
dimensions in step 5. Subagents exist here for **context isolation** (a fresh, small context per
task), not for role-play.

## Models: roles, resolved in one place

Skills, agent prompts and this README refer to **roles** - `planner`, `plan-reviewer`,
`executor`, `reviewer`, `external-reviewer`, `cheap`. The only file that maps roles to models is
[`model-routing.md`](skills/agentic-loop/references/model-routing.md). Claude Code needs a literal
`model:` in agent frontmatter, so `bin/check-models.py --fix` generates those lines from the role
map, and `check-models.py` fails if anything else names a model (`install.sh` warns,
`release.sh` refuses).

| Agent | Role | Job |
|-------|------|-----|
| `agentic-loop-plan-review` | `plan-reviewer` | step 3 - plan quality gate |
| `agentic-loop-quality` | `reviewer` | review - best practices |
| `agentic-loop-implementation` | `reviewer` | review - conformance to plan |
| `agentic-loop-testing` | `reviewer` | review - coverage / edge cases |
| `agentic-loop-documentation` | `reviewer` | review - comments / docstrings |
| `agentic-loop-simplification` | `reviewer` | review - redundancy / YAGNI |
| `agentic-loop-fixer` | `executor` | applies confirmed findings, repairs a red gate |
| `agentic-loop-external-review` | `external-reviewer` | step 7 - adversarial fresh-context pass |

## Differences from the Cursor original

| Cursor | Here |
|--------|------|
| `.cursor/skills/`, `.cursor/agents/` | `~/.claude/skills/`, `~/.claude/agents/` |
| `Task` tool with `model:` slugs (Grok / Sol / Gemini) <!-- models-ok --> | `Agent` tool; `model:` accepts Claude aliases (`opus` / `sonnet` / `haiku`), generated from the role map <!-- models-ok --> |
| Parent model gate on the vendor's 1M-context models | Parent gate asks you to run `/model <planner>` |
| Step 7 external review = a different model family (Gemini) <!-- models-ok --> | Step 7 = `external-reviewer` role, fresh adversarial context (not cross-family - see model-routing.md) |
| Cursor hooks expose per-turn tokens | Telemetry reads `message.usage` from the session and subagent transcripts |
| `~/.cursor/hooks.json` | `~/.claude/settings.json` `hooks` block |
| `.cursor/skills/.../*.md` uses repo-relative paths, rewritten on install/sync | Every reference is already the absolute `~/.claude/...` path — no rewriting needed either direction |

Carried over as-is: the stages, the gates, the session-docs mandate
(`docs/agentic/yyyymmdd-<slug>/`), the `.llm/manifest.json` + `.gitignore` rules, the
Stage-report-after-every-step discipline, the 5-parallel-reviewers-then-fixer loop.

## Telemetry

```bash
T=~/.claude/agentic-loop/hooks/telemetry-report.py
python3 $T status
python3 $T mark   "Step 4 · Plan Exec"
python3 $T report --step 4 --name "Plan Exec"
python3 $T summary            # per-step wall, parent + subagent tokens, findings, gate runs
python3 $T yield              # review acceptance rate per reviewer, across all projects
```

The `SessionStart` hook records the live transcript path in
`<project>/.llm/telemetry/session.json`, and every hook event records its transcript, so a loop
resumed across several sessions is still summed completely. The reporter collapses the
transcript's per-content-block rows by message id (summing rows over-counts tokens 2-3x), adds
subagent usage from `<session>/subagents/agent-*.jsonl`, and reports the parent's last prompt
size as `context`.

Ledger location: `<project>/.llm/telemetry/` when `.llm/` exists, else
`~/.claude/agentic-loop/telemetry/<project>-<hash>/`, overridable with
`$CLAUDE_LOOP_TELEMETRY_DIR`. Never committed (`.gitignore` + a self-ignoring
`.gitignore` in the dir).

## Project files the loop maintains

| Path | Committed | What |
|------|-----------|------|
| `.llm/manifest.json` | yes | navigation index |
| `.llm/verify.json` | yes | verify gate commands |
| `.llm/loop-state.json` | no | checkpoint for resume |
| `.llm/verify/` | no | gate results + logs |
| `.llm/telemetry/` | no | hook ledger |
| `docs/agentic/<session>/` | project's choice | brainstorm, planning, progress, telemetry |
| `docs/plans/` | yes | executable plans |

## Publishing a new version (maintainer workflow)

```bash
# 1. You edited an installed skill/agent/script directly in ~/.claude while testing it.
#    Pull those edits back into the repo (stages them, shows a diff, doesn't push):
./sync-from-local.sh
./sync-from-local.sh --commit "tune plan-exec retry wording"
./sync-from-local.sh --commit "..." --push

# 2. Changed a model? Edit the Role map in model-routing.md, then:
python3 bin/check-models.py --fix

# 3. Cut a release: bump VERSION, prepend a CHANGELOG entry, commit + tag.
./release.sh patch            # 1.1.0 -> 1.1.1
./release.sh minor --push     # 1.1.1 -> 1.2.0, and push commit + tag
./release.sh 2.0.0            # set an explicit version
```

`sync-from-local.sh` never pushes unless you pass `--push`. `release.sh` never pushes
unless you pass `--push`, and refuses to release with model-routing drift. Neither force-pushes
or touches anything outside `skills/`, `agents/`, `hooks/`, `bin/`, `VERSION`, `CHANGELOG.md`.

Client machines stay on `install.sh` - they never need these scripts.

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
│   ├── agentic-loop/SKILL.md + references/{model-routing,limits,verify-gate,loop-state,
│   │                          context-discipline,stage-report,session-docs,step-minus-one,telemetry-hooks}.md
│   ├── agentic-loop-brainstorm/SKILL.md
│   ├── agentic-loop-plan-make/SKILL.md + references/plan-template.md
│   ├── agentic-loop-plan-exec/SKILL.md + references/task-prompt.md
│   ├── agentic-loop-review/SKILL.md + references/{reviewers,fixer}.md
│   └── agentic-loop-docs-pr/SKILL.md
├── agents/agentic-loop-*.md          (8 subagents)
├── bin/
│   ├── verify-gate.py                (deterministic build/lint/test gate)
│   ├── loop-state.py                 (checkpoint, caps, resume)
│   ├── check-models.py               (role map -> agent frontmatter, drift check)
│   ├── eval.py                       (record / run / report / compare)
│   └── _common.py
├── evals/README.md                   (eval harness guide; cases live in ~/.claude, not here)
└── hooks/
    ├── telemetry-collect.sh / .py    (hook entrypoint)
    ├── telemetry-report.py           (mark / report / findings / yield / summary / status)
    ├── merge-hooks.py                (settings.json wiring, --uninstall)
    ├── _ledger.py                    (shared ledger-path logic)
    └── hooks.template.json
```

## Credit

Workflow design, stage structure, prompts, and telemetry approach ported from
[superboyAmira/cursor-agentic-loop](https://github.com/superboyAmira/cursor-agentic-loop),
inspired by [umputun/cc-thingz](https://github.com/umputun/cc-thingz).
