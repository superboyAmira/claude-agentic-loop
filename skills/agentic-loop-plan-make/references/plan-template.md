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

## Development Approach
- **testing approach**: [TDD / Regular]
- Complete each task fully before the next
- Small, focused changes
- Every task MUST include new/updated tests for its code changes
- All tests must pass before starting the next task
- Update this plan file when scope changes during implementation

## Testing Strategy
- **unit tests**: required for every implementation task
- **e2e / integration**: if the project has them and the change touches those surfaces

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
- [ ] run tests — must pass before next task

### Task N-1: Verify acceptance criteria
- [ ] verify Overview requirements are met
- [ ] run full relevant test suite
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
