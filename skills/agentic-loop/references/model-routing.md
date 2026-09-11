# Model routing (agentic-loop)

## Can Claude Code switch models by itself?

| Layer | Can agent switch? | How |
|-------|-------------------|-----|
| **Parent chat** | **No** | User picks with `/model`. |
| **Subagents (`Agent` tool)** | **Yes** | `model` in `~/.claude/agents/*.md` frontmatter, or the `model` arg to the `Agent` tool. Values: `opus`, `sonnet`, `haiku`, `inherit`. |
| **Context / effort** | **No** | Claude Code has no per-call context-window or reasoning-effort knob. |

## Required routing

| Steps | Role | Model | Mechanism |
|-------|------|-------|-----------|
| **-1** | Markup bootstrap (missing manifest etc.) | `sonnet` | `Agent` tool, `subagent_type: general-purpose`, `model: sonnet` — or `agentic-loop` runs it inline |
| **0-2** | Parent (index, brainstorm, plan-make dialogue) | **Opus** | User runs `/model opus`. The loop asks for this at Step 0. |
| **3** | Plan auto-review | `opus` | `agentic-loop-plan-review` (pinned) |
| **4** | Task implementers + fixer | `sonnet` | `agentic-loop-fixer` + `general-purpose` implementers |
| **5-6, 8** | 5 reviewers + smells + critical + fixer | `sonnet` | `agentic-loop-{quality,implementation,testing,documentation,simplification,fixer}` |
| **7** | External review | `opus` | `agentic-loop-external-review` |
| **9-10** | Docs/PR + handoff | `sonnet` | `agentic-loop-docs-pr` |

## Slugs

```text
BOOTSTRAP          = sonnet
PLANNING_PARENT    = opus          # user-selected via /model opus
PLAN_REVIEW_AGENT  = opus          # agentic-loop-plan-review
EXEC_IMPLEMENTER   = sonnet
EXEC_REVIEW        = sonnet
EXTERNAL_REVIEW    = opus          # agentic-loop-external-review
```

## Step 7 external-review caveat

The Cursor original routes Step 7 to a **different model family** (Gemini) for a genuinely
independent perspective. Claude Code only has Claude models, so `agentic-loop-external-review`
runs on `opus` with a strict "you did not write this code, be adversarial" system prompt. It
is still worth running — a fresh context with an adversarial brief catches real issues — but
it is *not* a cross-family check. If you have another CLI/model available (e.g. `gh copilot`,
a local model, another vendor's CLI), run it by hand on `git diff <default>...HEAD` and feed
findings to the fixer as an extra pass.

## Parent gate for planning (steps 0-2)

If steps 0-2 (deep brainstorm / plan-make) are about to run and `/model` is on Sonnet or
Haiku, and the user has not explicitly opted in:

1. **Stop** before deep design / plan authoring (Step -1 bootstrap on Sonnet is fine).
2. Ask the user to run `/model opus`.
3. Do not silently continue deep planning on a small model.

Exceptions: `skip model gate`, `from-plan`, `review-only`.

## Steps 0-2: no subagent fan-out

| Allowed | Forbidden |
|---------|-----------|
| Parent (Opus) tools: Read/Glob/Grep/Bash | `Agent` fan-out to "map the repo" during brainstorm/plan-make |
| Optional `Agent` on `opus` only, synthesized in parent | Parallel research subagents on `sonnet`/`haiku` during 0-2 |
| `agentic-loop-plan-review` at step 3 | — |

Step **-1** is the exception: markup bootstrap may use a `sonnet` subagent.

If a pinned model is unavailable, announce the fallback and continue with the closest tier
(`opus` -> `sonnet`).
