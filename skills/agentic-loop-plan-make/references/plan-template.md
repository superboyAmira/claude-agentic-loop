# [Plan Title]

## Overview
- What changes and why
- Problem solved / key benefits
- How it integrates with the existing system
- Session docs: `docs/agentic/yyyymmdd-<slug>/` (brainstorm.md, planning.md, needs-documenting.md)

## Context (from discovery)
- Files/components involved:
- Related patterns found:
- Dependencies:

## Constraints
<!-- Every constraint from brainstorm/planning, one line each. Task subagents get this section
     verbatim; it survives compaction because it lives in the file, not in chat. -->
- e.g. keep the public API backwards-compatible
- e.g. no new dependencies

## Development Approach
- **testing approach**: [TDD / Regular]
- Complete each task fully before the next
- Small, focused changes
- Every task MUST include new/updated tests for its code changes
- The verify gate must be green before the next task starts
- Never delete, skip or weaken existing tests to make a task pass
- Update this plan file when scope changes during implementation

## Testing Strategy
- **unit tests**: required for every implementation task
- **e2e / integration**: if the project has them and the change touches those surfaces

## Verification
- Gate: `.llm/verify.json` - [list its steps, e.g. build · vet · lint · test]
- The orchestrator runs the gate after every task and before reviews (step 4.5); a task is done
  only when its checkboxes are `[x]` and the gate is green
- Tasks that are red by design (TDD: tests before code) say so explicitly:
  `(fails until Task N)`

## Progress Tracking
- Mark completed items with `[x]` immediately when done
- Add newly discovered tasks with a `+` prefix
- Document blockers with a `!` prefix

## Solution Overview
- Chosen approach and rationale
- Key design decisions

## Technical Details
- Data structures / API / config changes
- Processing flow

## Implementation Steps

### Task 1: [specific name]

**Files:**
- Create: `path/to/new`
- Modify: `path/to/existing`

- [ ] specific implementation step
- [ ] specific implementation step
- [ ] write tests for success cases
- [ ] write tests for error/edge cases
- [ ] run the task's tests - must pass before next task

### Task N-1: Verify acceptance criteria
- [ ] verify Overview requirements are met
- [ ] run the full verify gate (`verify-gate.py run`) - green
- [ ] verify edge cases handled

### Task N: Update documentation
- [ ] update README / CLAUDE / AGENTS / project docs if needed
- [ ] move this plan to `docs/plans/completed/` when execution finishes

## Documentation
- Brainstorm/planning dialogue captured under `docs/agentic/yyyymmdd-<slug>/`
- Extra docs debt tracked in `needs-documenting.md` (promote in Docs & PR step)

## Post-Completion
*Manual / external items — no checkboxes*

- Manual verification scenarios
- Deploy / config / consuming projects
- Unresolved items from `needs-documenting.md`
