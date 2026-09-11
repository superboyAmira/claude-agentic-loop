# Reviewer prompts (fallback if pinned subagents are missing)

Substitute: `DEFAULT_BRANCH`, `PLAN_FILE_PATH` (or "none").

All reviewers are **read-only**. Severity: `CRITICAL` | `MAJOR` | `MINOR` | `NIT`.
Model for these fallbacks: `sonnet` (`Agent` tool, `subagent_type: general-purpose`).

---

## quality — Best practices

Correctness, edge cases, error handling, races, leaks, insecure patterns, API breaks. Ignore
pure style nits unless they hide bugs.

---

## implementation — Conformance to the plan

Compare the diff to `PLAN_FILE_PATH`. Missing pieces? Scope creep? Wrong layer?

---

## testing — Coverage, edge cases

Missing success/error cases, brittle tests, untested new branches.

---

## documentation — Comments, docstrings

Misleading/stale comments, missing docs when behavior changes. No docs for trivial renames.

---

## simplification — Redundancy

Unnecessary abstractions, dead code from the change, YAGNI violations.

---

## smells

Project conventions (CLAUDE.md, AGENTS.md, .claude/rules), duplication vs abstraction,
naming/layout/logging patterns.

---

## external (opus, independent brief)

Independent adversarial review. You did not write this code. Tag `CRITICAL` / `MAJOR` /
`MINOR`. Clean -> `NO ISSUES FOUND`.
