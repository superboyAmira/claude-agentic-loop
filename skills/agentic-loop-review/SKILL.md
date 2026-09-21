---
name: agentic-loop-review
description: >-
  Multi-phase post-implementation review behind a deterministic verify gate:
  5 parallel agents (Quality, Implementation, Testing, Documentation,
  Simplification) -> Fixer loop, then code smells, external review
  (independent brief), critical-only; the gate re-runs after every fixer and
  review yield is recorded per reviewer. Use when the user says
  agentic-loop-review, review, agentic review, code smells, external review,
  critical review, or when agentic-loop-plan-exec / agentic-loop reaches the
  review phases.
---

# Review (agentic multi-phase)

Post-implementation multidimensional review. Inspired by cc-thingz + the Agent Review pattern.

**Roles:** reviewers = `reviewer`, fixer = `executor`, external = `external-reviewer` with an
independent-reviewer brief (roles resolve in `~/.claude/skills/agentic-loop/references/model-routing.md`).
Prefer the pinned `agentic-loop-*` subagents in `~/.claude/agents/` (models set in
frontmatter), invoked via the `Agent` tool with `subagent_type`.

LLM review comes **after** the deterministic gate, never instead of it. Caps and termination
conditions: `~/.claude/skills/agentic-loop/references/limits.md`.

```bash
L=~/.claude/agentic-loop
G="python3 $L/bin/verify-gate.py"; S="python3 $L/bin/loop-state.py"; T="python3 $L/hooks/telemetry-report.py"
```

After each review phase: `$S step N done`, Stage report
(`~/.claude/skills/agentic-loop/references/stage-report.md`) with the `gate` and `findings` lines.

## When invoked

- After `agentic-loop-plan-exec` finishes tasks and step 4.5 is green
- Standalone: review the current branch/diff against a plan (or HEAD vs default branch)

## Setup

1. Resolve the default branch (`main` / `master` / `trunk`).
2. Diff: `git diff <default>...HEAD` (else staged/unstaged).
3. Pass the plan path to reviewers when known.
4. **Gate precondition:** `$G check`. Not green (red, stale, or never run) -> run step 4.5
   (`$G run --label 4.5` + repair loop from verify-gate.md). **Phase 1 does not start on red.**
5. Append phase notes to `docs/agentic/<session>/progress.md` if present.

## Shared mechanics (every phase)

**Finding IDs.** Reviewers prefix each finding with an ID (`Q` quality, `I` implementation,
`T` testing, `D` documentation, `S` simplification, `SM` smells, `X` external, `C` critical;
numbering restarts each iteration) and report at most 15 findings, most severe first.

**Fixer.** Spawn `agentic-loop-fixer` (or `general-purpose` + [references/fixer.md](references/fixer.md))
with the **verbatim** findings, plus the list of findings rejected in earlier iterations of this
phase. It answers per ID: `fixed:` / `rejected:` (incl. `needs-plan-change:`). Show FIXES to the user.

**Gate after every fixer run.** `$G run --label <step>`. Red -> repair loop
(`$S bump verify_repairs --scope <step>`, fixer with the failing tails as `G1…`, re-run; exit 3 ->
escalate). The next iteration or phase never starts on red.

**Yield telemetry.** After the fixer, per reviewer that ran (clean ones with `--total 0`):
`$T findings --step <step> --reviewer <name> --iteration <i> --total N --accepted A --rejected R --severe-accepted S`.

**Anti-repetition.** Before the fixer, drop findings that repeat an already-rejected one (count
them as rejected). Pass the rejected list to the next iteration's reviewers: "already rejected -
do not re-raise without new evidence".

**Plan-level findings.** `needs-plan-change` rejections -> `$S open add --step <step> ...`;
at the end of the step ask the user (limits.md: add `+` tasks and re-enter step 4 / defer / stop).

## Phase 1 (step 5) - Agent Review (5 parallel -> Fixer loop)

Report: `--- Review phase 1: Agent Review (5 parallel) ---`

### Parallel reviewers (always all five, one message)

Launch from the **orchestrator (this session)** in **one** message with five `Agent` tool
calls (`run_in_background: false` so results return together):

| subagent_type | ID | Focus |
|---------------|----|-------|
| `agentic-loop-quality` | Q | Best practices |
| `agentic-loop-implementation` | I | Conformance to the plan |
| `agentic-loop-testing` | T | Coverage, edge cases |
| `agentic-loop-documentation` | D | Comments, docstrings |
| `agentic-loop-simplification` | S | Redundancy |

If the pinned subagents are unavailable, spawn 5x `general-purpose` with `model: <reviewer>` and
the prompts from [references/reviewers.md](references/reviewers.md).

### Loop: review -> fixer -> gate -> review

Before each iteration: `$S bump review_iterations --scope 5` (exit 3 -> stop cycling).

1. Collect **full** outputs (do not filter or dismiss).
2. All five clean (`NO ISSUES FOUND`) -> phase done.
3. Else fixer -> gate -> yield telemetry.
4. **No progress** (the fixer fixed nothing) -> phase done.
5. Otherwise next iteration, all five reviewers again.

Stopped by the cap or no progress with findings left -> list the leftovers to the user, record
unresolved CRITICAL/MAJOR with `$S open add --step 5`, continue to phase 2. Never drop findings silently.

## Phase 2 (step 6) - Code smells

Report: `--- Review phase 2: code smells ---`

1. One `Agent` (`general-purpose`, `model: <reviewer>`) with the smells prompt (IDs `SM`).
2. If findings -> fixer -> gate -> yield telemetry (`--reviewer smells`).
3. Single pass, then continue.

## Phase 3 (step 7) - External review (independent brief)

Report: `--- Review phase 3: external review (independent) ---`

Use `agentic-loop-external-review` (IDs `X`). See the caveat in
`~/.claude/skills/agentic-loop/references/model-routing.md` — this is a fresh-context
adversarial pass, not a cross-family check.

Adversarial loop, `$S bump external_iterations --scope 7` before each round (exit 3 -> stop):

1. External review of the diff vs the plan; severities `CRITICAL` / `MAJOR` / `MINOR`.
2. `NO ISSUES FOUND` -> done.
3. Else -> fixer -> gate -> yield telemetry (`--reviewer external`).
4. No CRITICAL/MAJOR remaining after fixes, or no progress -> done (minors fixed once).
5. Blocking issues remain -> next round.

## Phase 4 (step 8) - Critical only

Report: `--- Review phase 4: critical/major only ---`

One pass: `agentic-loop-quality` + `agentic-loop-implementation` asked for CRITICAL/MAJOR only
(IDs `C`) -> fixer if needed -> gate -> yield telemetry (`--reviewer critical-quality` /
`critical-implementation`).

Step 8 ends with `$G check` green.

## Hard rules

- No phase starts on a red or stale gate; the orchestrator's `verify-gate.py` is the only gate
- Fan-out from the **orchestrator** (this session), never from nested subagents
- Never dismiss findings as pre-existing — the fixer decides
- Pass findings verbatim to the fixer
- Record yield for every reviewer invocation, clean ones included
- No push; commits only if the user explicitly asked
