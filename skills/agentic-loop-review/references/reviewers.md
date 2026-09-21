# Reviewer prompts (fallback if pinned subagents are missing)

Substitute: `DEFAULT_BRANCH`, `PLAN_FILE_PATH` (or "none"), `REJECTED` (findings rejected in
earlier iterations of this phase, or "none").

All reviewers are **read-only**. Role for these fallbacks: `reviewer` (`Agent` tool,
`subagent_type: general-purpose`, `model: <reviewer>` from model-routing.md).

Output contract for every reviewer:

- One line per finding: `<ID> <SEVERITY> <path>:<line> | <problem> | <suggested fix>`
- Severity: `CRITICAL` | `MAJOR` | `MINOR` | `NIT`
- At most 15 findings, most severe first; if more exist, end with `+N more MINOR/NIT omitted`
- Do not re-raise anything in `REJECTED` unless you have new evidence (say what it is)
- Clean -> exactly `NO ISSUES FOUND`

---

## quality - Best practices (ID `Q`)

Correctness, edge cases, error handling, races, leaks, insecure patterns, API breaks. Ignore
pure style nits unless they hide bugs.

---

## implementation - Conformance to the plan (ID `I`)

Compare the diff to `PLAN_FILE_PATH` (including its Constraints). Missing pieces? Scope creep?
Wrong layer?

---

## testing - Coverage, edge cases (ID `T`)

Missing success/error cases, brittle tests, untested new branches, tests that were deleted,
skipped or weakened.

---

## documentation - Comments, docstrings (ID `D`)

Misleading/stale comments, missing docs when behavior changes. No docs for trivial renames.

---

## simplification - Redundancy (ID `S`)

Unnecessary abstractions, dead code from the change, YAGNI violations.

---

## smells (ID `SM`)

Project conventions (CLAUDE.md, AGENTS.md, .claude/rules), duplication vs abstraction,
naming/layout/logging patterns.

---

## external - independent brief (ID `X`)

Independent adversarial review. You did not write this code. Tag `CRITICAL` / `MAJOR` /
`MINOR`. Clean -> `NO ISSUES FOUND`.

---

## critical - phase 4 (ID `C`)

Same focus as quality / implementation, but report only `CRITICAL` and `MAJOR`.
