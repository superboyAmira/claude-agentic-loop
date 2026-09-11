---
name: agentic-loop-brainstorm
description: >-
  Collaborative design dialogue before implementation — idea to approaches to
  design to plan. Writes the full dialogue into docs/agentic/... structured
  docs. Use when the user says agentic-loop-brainstorm, brainstorm, let's
  brainstorm, help me design, explore options for, think through, or wants
  thorough analysis before coding.
---

# Brainstorm

Turn ideas into designs through collaborative dialogue **before** implementation.
Inspired by [cc-thingz brainstorm](https://github.com/umputun/cc-thingz).

## Model

Agentic-loop **step 1**. Parent: **Opus** (`/model opus`). If the picker is on Sonnet/Haiku,
stop and ask the user to switch — see
`~/.claude/skills/agentic-loop/references/model-routing.md`.

### Hard ban: no research subagent fan-out

Brainstorm is a **parent-only dialogue**, not a fan-out job.

- **Do NOT** launch `Agent` / Explore subagents to map the codebase.
- Gather context with Read/Glob/Grep/Bash in this parent session.
- If parallel research is unavoidable, only `opus` subagents; synthesize in the parent.
- Never treat a subagent map as the brainstorm outcome.

## Documentation (mandatory)

Follow `~/.claude/skills/agentic-loop/references/session-docs.md`.

Before leaving this skill:

1. Create/update `docs/agentic/yyyymmdd-<slug>/brainstorm.md` with the **full** Q&A,
   approaches, selected design, open questions.
2. Create/update `needs-documenting.md` — what else still needs project docs (README, business
   process, ADR, API, metrics, manifest entries).
3. Create `README.md` in the session folder if missing.
4. Chat-only brainstorm = **incomplete**.

## Custom rules (optional)

`.claude/brainstorm-rules.md` in the project (project wins).

## Process

### Phase 1: Understand

1. Gather context: files, docs, `git log --oneline -10`.
2. Prefer `.llm/manifest.json`, `CLAUDE.md`, `AGENTS.md`, `README.md`.
3. Ask questions **one at a time** (multiple choice preferred).
4. Focus: purpose, constraints, success criteria, integration points.
5. Append each Q&A to `brainstorm.md` as you go (or flush at end — but do not skip).

### Phase 2: Explore approaches

1. Propose **2-3** approaches with trade-offs; lead with a recommendation.
2. Wait for user choice. Record in `brainstorm.md`.

Skip only if obvious / user already specified.

### Phase 3: Present design

1. Sections ~200-300 words; validate each with the user.
2. Cover architecture, components, data flow, error handling, testing.
3. Persist validated design into `brainstorm.md`.

### Phase 4: Next steps

| Option | Action |
|--------|--------|
| Write plan | Flush session docs -> Stage report -> `agentic-loop-plan-make` |
| Start now | Only if tiny scope; still write session docs |
| Done | Session docs written; stop |

After the step: Stage report per
`~/.claude/skills/agentic-loop/references/stage-report.md`.

## Principles

- One question per message; multiple choice when possible
- YAGNI; lead with recommendation
- Prefer duplication over premature abstraction when unclear — ask

## Output

No production code here. Design + structured docs only. Plans via `agentic-loop-plan-make`.
