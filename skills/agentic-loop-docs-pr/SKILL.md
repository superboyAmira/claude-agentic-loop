---
name: agentic-loop-docs-pr
description: >-
  Finalize documentation and open a pull request after agentic-loop or
  agentic-loop-plan-exec. Updates plan completed/, drafts the PR summary, pushes
  with user consent, creates the PR via gh. Use when the user says
  agentic-loop-docs-pr, docs-pr, open PR, create PR after the loop, or
  agentic-loop reaches Docs & PR.
---

# Docs & PR

Finalize docs and create a PR after implementation + reviews.
Maps to diagram step **9 · Docs & PR** before human review.

## Model

The `cheap` role is enough for the parent here (roles resolve in
`~/.claude/skills/agentic-loop/references/model-routing.md`).

## Preconditions

- Feature branch with the intended commits (or ask the user to commit first)
- Reviews from `agentic-loop-review` done (or the user explicitly skips)
- `loop-state.py show`: no unresolved `open_findings` the user has not seen - list them for the PR body

## Steps

### 1. Docs pass

Process `docs/agentic/<session>/needs-documenting.md` and the brainstorm/planning session docs:

- promote checklist items into real project docs when in scope
- update `.llm/manifest.json` for new docs
- leave unresolved items listed in the PR body

1. Diff vs the default branch: what user-facing / operator-facing behavior changed?
2. Update only what is needed: README, CLAUDE.md, AGENTS.md, `docs/` — no unsolicited markdown
   sprawl.
3. If a plan file exists and all tasks/reviews are done:
   `mkdir -p docs/plans/completed && git mv <plan> docs/plans/completed/` (or move if
   untracked).

### 2. Commit (only if the user asks or explicitly opted in)

Follow the repo's commit rules / user git rules. Prefer one focused commit for docs + plan
move. Never `--no-verify`. Never push until step 3 confirms.

### 3. Gate, then push + PR

1. `python3 ~/.claude/agentic-loop/bin/verify-gate.py check`. Not green (the docs pass or a
   commit changed code, or the last run was red) -> `verify-gate.py run --label 9` + repair loop
   (verify-gate.md). **No push and no PR from a red or stale gate.**
2. Ask before push if not already confirmed in this session.

```bash
git push -u origin HEAD
gh pr create --title "..." --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...

## Agentic loop
- Plan: `docs/plans/completed/...`
- Verify gate: green (<steps from .llm/verify.json>)
- Reviews: agent / smells / external / critical - done; accepted/total findings: <from summary>
- Open findings: <from loop-state, or none>
EOF
)"
```

Use `gh` for GitHub. If a GitLab remote, use `glab` only if available; otherwise give the user
the compare URL.

### 4. Hand off (step 10)

Return:

- PR URL
- Short summary of decisions/deviations from `docs/agentic/<session>/progress.md` (if any)
- Explicit: **Human Review** — your turn; the agent stops unless asked to address review
  comments

Then `loop-state.py step 10 done` and `loop-state.py done`.

## Do not

- Force-push
- Merge the PR
- Skip tests "to get the PR up" if the branch is red - the gate blocks it; escalate instead

## Telemetry

Emit a Stage report after the docs pass and after PR creation (`stage-report.md`), then the
**Loop cost summary**.
