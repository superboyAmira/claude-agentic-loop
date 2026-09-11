# Collecting real telemetry in Claude Code

Stage reports must not guess numbers. Claude Code writes a full transcript JSONL per session,
and every assistant message carries a `message.usage` block. The collector reads that ledger
instead of writing `n/a`.

## What is available

| Field in Stage report | Source | Notes |
|---|---|---|
| `tokens` | transcript `message.usage` per assistant message | `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` |
| `model_parent` | transcript `message.model` | e.g. `claude-opus-5` |
| `wall_time` | `SessionStart` / `Stop` hook timestamps + `mark` timestamps | join on the step mark |
| `agents_used` | `SubagentStop` hook events | subagent finished; no token attribution |
| `tools` | transcript `tool_use` blocks | counts by name |
| `files_touched` | transcript `Edit`/`Write` tool inputs | dedup by path |
| `context` | **not exposed** | always `n/a` |

Rules the collector respects:

1. Transcript `input_tokens` does **not** include the cache fields; a turn's total input is
   `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
2. `Stop` fires per **turn**; a step spanning several user messages aggregates several turns —
   the report says `over N turn(s)`.
3. Token fields can be absent on some message types; treat as `0` only when the message is an
   assistant turn that produced output.
4. Subagent token usage is not attributed in the parent transcript. Report subagent cost as
   duration + tool calls from `SubagentStop`.

## Install the collector

`install.sh` copies the collector to `~/.claude/agentic-loop/hooks/` and merges hook wiring
into `~/.claude/settings.json` (`SessionStart`, `Stop`, `SubagentStop`, `PreCompact`,
`SessionEnd`). Existing hooks are preserved; re-running is idempotent.

```bash
cd ~/.claude/agentic-loop && ./install.sh          # skills + agents + hooks
cd ~/.claude/agentic-loop && ./install.sh --no-hooks # skip telemetry
```

From then on **every project on this machine** collects telemetry — nothing per repo.

To remove the hook wiring:

```bash
python3 ~/.claude/agentic-loop/hooks/merge-hooks.py --uninstall
```

The collector is safe for a hot path: it whitelists scalar fields only (never prompt text,
thinking text, diffs or tool output), appends one JSON line per event, rotates at 20 MB, and
always exits `0` so a broken collector can never block the agent.

### Where the ledger lands

- `<workspace>/.llm/telemetry/events.jsonl` when the project has a `.llm/` directory (Step -1
  creates it) — plus `session.json` recording the active transcript path
- `~/.claude/agentic-loop/telemetry/<project-hash>/events.jsonl` otherwise
- `$CLAUDE_LOOP_TELEMETRY_DIR` overrides both

The ledger is never committed: `.gitignore` lists `.llm/telemetry/`, and the collector drops a
self-ignoring `.gitignore` (`*`) into the directory.

## Use it during the loop

```bash
# at the start of each step
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py mark "Step 6 · Code smells"

# when the step ends -> paste into chat + telemetry.md
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py report --step 6 --name "Code smells"

# before Docs & PR / stop
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py summary

# sanity check that hooks are firing
python3 ~/.claude/agentic-loop/hooks/telemetry-report.py status
```

Run these from the project directory — the reporter resolves the ledger from the cwd.

`report` prints the Stage report block with every measurable field filled and `<fill: …>`
placeholders for judgement fields. Fill those yourself; never ship placeholders.

## Caveats

- Hook telemetry covers the **parent** agent's tokens. Subagent token usage is not exposed;
  it still lands in your billing, so treat the parent total as a lower bound.
- `wall_time` from marks includes user-gate waits. Note idle time separately.
- Cloud / headless runs may not load user hooks — report `n/a (hooks not loaded)`.
- If `status` shows the transcript path is stale, run any prompt once so `SessionStart`
  refreshes `session.json`.
