# Context discipline

A 1M-token window is not 1M useful tokens: recall degrades well before the window is full
("context rot"). The loop manages context instead of buying more of it. Aim for the smallest
set of high-signal tokens per agent.

## Rules

1. **Fresh context per plan task.** Every task runs in a new subagent whose prompt carries only:
   - the plan path and **its own** task section (title, Files block, unchecked items);
   - the `.llm/manifest.json` entries whose `path` or `tags` match the task's Files block;
   - project rules by path (CLAUDE.md, AGENTS.md, `.claude/rules/`), not pasted;
   - the plan's Constraints section;
   - retry notes (on a retry only).

   Never paste chat history, brainstorm transcripts, other tasks' diffs or full logs.

2. **Distilled returns.** Task subagents return at most ~15 lines (what changed, files, test
   result, decisions logged). Reviewers return at most 15 findings, one line each. Raw material
   stays in files the next agent can open (`git diff`, `.llm/verify/last.json`, logs).

3. **The orchestrator reads summaries, not raw material.** Do not read large diffs or logs in the
   parent session; hand their paths to the subagent that needs them.

4. **Persist before it is lost.** Anything that must survive compaction goes to a file first:
   decisions -> `progress.md`, subtle constraints ("keep backwards-compatible", "no new deps")
   -> the plan's Constraints section, loop position -> `loop-state.json`. Compaction silently drops
   such details; files do not.

5. **Watch the size.** The Stage report's `context:` line is the size of the parent's last
   prompt, read from the transcript. Above `context_warn_tokens` ([limits.md](limits.md)),
   recommend to the user at the next step boundary: `/compact`, or end the session and run
   `/agentic-loop resume` in a fresh one. Natural cut points: after step 3 (plan approved) and
   after step 4.5 (gate green). Claude Code does not let the skill compact by itself.

6. **Steps 0–2 stay parent-only.** The design dialogue needs one coherent context; no research
   fan-out there (see model-routing.md).

## Why sequential, not a team of agents

Plan tasks run one at a time, and reviewers are the only parallel fan-out. That is deliberate:
coding tasks share state (the same files, the same build), so parallel implementers mostly
produce merge conflicts and duplicated work, at several times the token cost. Parallelism is used
where the work is independent and read-only: the five review dimensions in step 5.
