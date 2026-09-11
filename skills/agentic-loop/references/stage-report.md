# Stage telemetry (after every step)

After **each** completed step (-1…10), print a **Stage report** block in chat **before**
moving on. Do not skip. Also append the same block to `docs/agentic/<session>/telemetry.md`.

Print even when the step is still in progress (status: `in progress`) if you pause for user
Q&A; print again with `done` when the step finishes.

## Required format

Use this shape (field names fixed; fill real values or `n/a`):

```markdown
### Stage report — Step N · <Name>
- status: done | in progress | skipped | blocked
- model_parent: <id or unknown>
- models_subagents: [<id>, ...]
- agents_used: [<agentic-loop-*>, ...]
- tools: Read/Grep/Agent/Write/Bash/... (counts if known)
- files_touched: N (list key paths, max 10)
- tokens: <input/output/total from the transcript ledger; else `n/a (not exposed)`>
- context: <n/a — Claude Code does not expose this to skills>
- wall_time: <ISO local start->end or `Xm Ys`; mandatory when known>
- cost_notes: <mode notes; else brief fact>
- artifacts: <paths written this step>
- next: Step N+1 · <Name> | <concrete next action>
```

### Example

```markdown
### Stage report — Step 6 · Code smells
- status: done
- model_parent: claude-opus-5
- models_subagents: [claude-sonnet-5]
- agents_used: [agentic-loop-simplification (done, 45s), agentic-loop-fixer (done, 1m10s)]
- tools: Read x12 / Bash x4
- files_touched: 2 (internal/a.go, internal/b.go)
- tokens: in 1 180 993 / out 8 146 / total 1 189 139 over 6 turn(s)
- context: n/a
- wall_time: 12m 04s
- cost_notes: 1 subagent, single smells pass
- artifacts: internal/service/achievements/iron_reputation.go
- next: Step 7 · External review
```

## Where the numbers come from

Do **not** guess. Real tokens, durations and subagent stats come from the transcript ledger —
see [telemetry-hooks.md](telemetry-hooks.md) for the field map and install steps.

The collector is installed user-wide at `~/.claude/agentic-loop/hooks/` and wired into
`~/.claude/settings.json`. Run from the project directory:

```bash
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py mark "Step 6 · Code smells"   # at step start
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py report --step 6 --name "Code smells"   # at step end
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py summary                       # before Docs & PR
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py status                        # sanity check
```

`report` prints the Stage report block with every measurable field filled from the ledger and
`<fill: …>` placeholders for the judgement fields (`status`, `artifacts`, `next`). Fill those
in yourself — never ship a report with placeholders left in it.

If the collector is **not** installed: offer to run `~/.claude/agentic-loop/install.sh` once,
and until then report `tokens: n/a (hooks not installed)` rather than inventing numbers.

Key semantics when reading the raw ledger yourself:

- Per assistant message, `message.usage` carries `input_tokens`, `output_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens`. `input_tokens` in the transcript
  does **not** include the cache fields — total input for a turn is
  `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
- Subagent token usage is **not** attributed separately in the parent transcript — report
  subagent cost as duration + tool calls.
- If a step spans several user turns, the report says `over N turn(s)`.

## Rules

- Prefer real numbers from the ledger; then `/cost` output.
- Claude Code does not expose context-window usage to skills — `context: n/a` is correct.
- Include failed/retried subagents in the report.
- Keep the block compact; no essay.
- **wall_time is mandatory when the clock is known.** Include user-gate wait; note idle/abort
  separately. If unknown: `n/a`.
- Keep a running ledger for steps -1…10 in `telemetry.md`.
- Skipping the Stage report is a process failure — same severity as skipping session docs.

## Loop cost summary (after the last completed step, before Docs & PR / Stop)

Print this table even if some cells are `n/a`. Also write it to
`docs/agentic/<session>/telemetry.md`.

```markdown
### Loop cost summary
| Step | Name | Wall | Subagents | Tokens in/out/total | Notes |
|------|------|------|-----------|---------------------|-------|
| -1 | Markup | … | 0 | n/a | skipped |
| 0 | Index | … | 0 | … | |
| … | … | … | … | … | |
| **Σ** | | **…** | **N** | **…** | |

- session_wall: <first stage start -> now>
- idle_excluded: <optional: abort/user-away subtracted>
- tokens_source: transcript ledger | n/a (not exposed)
```

Do not skip the summary because tokens are missing — still show wall time and subagent counts.
