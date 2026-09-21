# Model routing (agentic-loop)

**This file is the only place that names models.** Every skill, agent prompt and the README refer
to a *role*; the Role map below resolves roles to models once. Models change every couple of
months; changing one means editing one line here.

To change a model:

1. Edit the Role map (and the Agent map if an agent changes role).
2. In the repo: `python3 bin/check-models.py --fix` - rewrites the `model:` line of the pinned
   agents in `agents/*.md` (Claude Code needs a literal model there, so it is generated from this map).
3. `./install.sh`.

`check-models.py` also fails when a skill, agent prompt or README line names a model outside this
file. `install.sh` warns on drift; `release.sh` refuses to release with drift.

## Role map

```text
# role              = model    # used for
planner             = opus     # parent for steps 0-2 (user switches with /model)
plan-reviewer       = opus     # step 3 plan review
executor            = sonnet   # step 4 task implementers, the fixer; enough for the parent in steps 3-10
reviewer            = sonnet   # steps 5, 6, 8 reviewers
external-reviewer   = opus     # step 7 adversarial fresh-context review
cheap               = sonnet   # step -1 markup bootstrap, step 9 docs/PR
```

## Agent map

```text
agentic-loop-plan-review      -> plan-reviewer
agentic-loop-quality          -> reviewer
agentic-loop-implementation   -> reviewer
agentic-loop-testing          -> reviewer
agentic-loop-documentation    -> reviewer
agentic-loop-simplification   -> reviewer
agentic-loop-fixer            -> executor
agentic-loop-external-review  -> external-reviewer
```

## Steps -> roles

| Steps | Role | Mechanism |
|-------|------|-----------|
| **-1** | `cheap` | `Agent` tool, `subagent_type: general-purpose`, `model: <cheap>` - or inline if the parent already runs `<cheap>` |
| **0-2** | `planner` | Parent. The user runs `/model <planner>`; the loop asks for it at Step 0 |
| **3** | `plan-reviewer` | `agentic-loop-plan-review` (pinned) |
| **4** | `executor` | `general-purpose` implementers with `model: <executor>`; `agentic-loop-fixer` (pinned) |
| **4.5** | - | `verify-gate.py`: no model involved |
| **5-6, 8** | `reviewer` (+ `executor` fixer) | `agentic-loop-{quality,implementation,testing,documentation,simplification}`; smells = `general-purpose` with `model: <reviewer>` |
| **7** | `external-reviewer` | `agentic-loop-external-review` (pinned) |
| **9-10** | `cheap` | Parent (`agentic-loop-docs-pr`) |

When a skill says `model: <executor>`, pass the model the Role map gives for that role as the
`model` argument of the `Agent` tool.

## Can Claude Code switch models by itself?

| Layer | Can agent switch? | How |
|-------|-------------------|-----|
| **Parent chat** | **No** | User picks with `/model`. |
| **Subagents (`Agent` tool)** | **Yes** | `model` in `~/.claude/agents/*.md` frontmatter, or the `model` arg to the `Agent` tool. Values: `opus`, `sonnet`, `haiku`, `fable`, `inherit`. |
| **Context / effort** | **No** | No per-call context-window or reasoning-effort knob for subagents. |

## Step 7 external-review caveat

The Cursor original routes Step 7 to a **different model family** (Gemini) for a genuinely
independent perspective. Claude Code only has Claude models, so `agentic-loop-external-review`
runs on the `external-reviewer` role with a strict "you did not write this code, be adversarial"
brief. It is still worth running - a fresh context with an adversarial brief catches real issues -
but it is *not* a cross-family check. If another vendor's CLI is available, run it by hand on
`git diff <default>...HEAD` and feed its findings to the fixer as an extra pass. Whether step 7
earns its cost is exactly what the review-yield telemetry answers (`telemetry-report.py yield`).

## Parent gate for planning (steps 0-2)

If steps 0-2 (deep brainstorm / plan-make) are about to run, the parent is not on the `planner`
model, and the user has not explicitly opted in:

1. **Stop** before deep design / plan authoring (Step -1 bootstrap on `cheap` is fine).
2. Ask the user to run `/model <planner>`.
3. Do not silently continue deep planning on a smaller model.

Exceptions: `skip model gate`, `from-plan`, `review-only`, `resume` past step 2, `eval`.

## Steps 0-2: no subagent fan-out

| Allowed | Forbidden |
|---------|-----------|
| Parent (`planner`) tools: Read/Glob/Grep/Bash | `Agent` fan-out to "map the repo" during brainstorm/plan-make |
| Optional `Agent` on the `planner` model only, synthesized in the parent | Parallel research subagents on smaller models during 0-2 |
| `agentic-loop-plan-review` at step 3 | — |

Step **-1** is the exception: markup bootstrap may use a `cheap` subagent.

If a pinned model is unavailable, announce the fallback and continue one tier down
(opus -> sonnet -> haiku).
