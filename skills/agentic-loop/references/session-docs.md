# Session documentation (brainstorm + planning)

The full dialogue during brainstorm and planning must land in **structured docs**, not only in
chat history.

## Where to write

Create a session folder once (slug from plan title / task id):

```text
docs/agentic/yyyymmdd-<slug>/
  README.md           # index of this session
  brainstorm.md       # structured brainstorm dialogue + decisions
  planning.md         # plan-make Q&A, approaches, constraints
  needs-documenting.md
  plan.md             # optional pointer/copy of docs/plans/...
```

Also keep the executable plan at `docs/plans/yyyymmdd-<slug>.md` (source of truth for `plan-exec`).

## brainstorm.md (required after step 1)

```markdown
# Brainstorm — <title>

## Goal
## Context discovered
## Questions & answers
| # | Question | Answer | When |
## Approaches considered
### A (recommended) / B / C — trade-offs
## Selected approach
## Design (validated sections)
## Open questions
## Rejected ideas
```

Capture **every** user answer from the one-at-a-time Q&A. Do not leave decisions only in chat.

## planning.md (required after step 2)

```markdown
# Planning notes — <title>
## Intent
## Scope / out of scope
## Constraints
## Testing approach
## Approach choice (link to brainstorm)
## Plan file
`docs/plans/yyyymmdd-<slug>.md`
## Deviations during planning
```

## needs-documenting.md (required; living list)

```markdown
# Needs documenting
- [ ] <topic> — why / for whom / suggested path (e.g. docs/business/…)
- [ ] Update `.llm/manifest.json` entries for new docs
- [ ] README / runbook / API / metrics / ADR if architecture changed
```

Promote items into real docs during step 9 (`agentic-loop-docs-pr`) or earlier if blocking.

## Business / operator docs vs session scratch

- Session folder (`docs/agentic/…`) = dialogue ledger for the loop; may be gitignored.
- Product business/runbook docs (e.g. `docs/business/<feature>.md`) = durable operator docs;
  **must be git-trackable**.
- If a business doc is created under an ignored path: un-ignore it (see `step-minus-one.md`
  manifest rules), add it to `.llm/manifest.json`, link it from the session README / plan.
- Never put ignored paths into `.llm/manifest.json`.

## Rules

- Write/update these files **before** leaving brainstorm / plan-make steps.
- Prefer updating existing session files over creating duplicates.
- Link session folder from the plan Overview.
- Match the project's docs language.
- After every step, print a Stage report (`stage-report.md`) and append to `telemetry.md`.
