# Collecting real telemetry in Claude Code

Stage reports must not guess numbers. Claude Code writes a full transcript JSONL per session,
every assistant message carries a `message.usage` block, and every subagent gets its own
transcript next to it. The reporter reads those instead of writing `n/a`.

## What is available

| Field in Stage report | Source | Notes |
|---|---|---|
| `tokens` (parent) | session transcript `message.usage` | `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` |
| `tokens` (subagents) | `<session>/subagents/agent-*.jsonl` `message.usage` | typed by `agent-*.meta.json` `agentType` |
| `model_parent` | most frequent `message.model` in the window | e.g. the `planner` model id |
| `models_subagents` | `message.model` in subagent transcripts | |
| `context` | usage of the parent's **last** message in the window | input + cache read + cache write = the size of that prompt |
| `wall_time` | transcript timestamps between marks | |
| `agents_used` | subagent transcripts (type, count, tokens) | falls back to `Agent` tool calls |
| `tools` | transcript `tool_use` blocks | counts by name |
| `files_touched` | transcript `Edit`/`Write` tool inputs | dedup by path |
| `gate` | `verify` events written by `verify-gate.py run` | |
| `findings` | `findings` events written by `telemetry-report.py findings` | |

Rules the reporter respects:

1. The transcript writes **one row per content block** and every row repeats the message's full
   `usage`. Rows are collapsed per `message.id` before summing - summing rows over-counts
   tokens by 2–3x.
2. Transcript `input_tokens` does **not** include the cache fields; a message's total input is
   `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
3. A loop that is resumed in a new session spans several transcripts. Every hook event records
   its `transcript_path`, and the reporter scans all of them, windowed by the step marks.
4. Messages with model `<synthetic>` (local placeholders) are ignored for `model_parent`.

## Install the collector

`install.sh` (run from the claude-agentic-loop clone) copies the scripts to
`~/.claude/agentic-loop/{hooks,bin}/` and merges hook wiring into `~/.claude/settings.json`
(`SessionStart`, `Stop`, `SubagentStop`, `PreCompact`, `SessionEnd`). Existing hooks are
preserved; re-running is idempotent.

```bash
cd <claude-agentic-loop clone> && ./install.sh              # skills + agents + scripts + hooks
cd <claude-agentic-loop clone> && ./install.sh --no-hooks   # skip telemetry wiring
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
- `~/.claude/agentic-loop/telemetry/<project>-<hash>/events.jsonl` otherwise
- `$CLAUDE_LOOP_TELEMETRY_DIR` overrides both (the eval harness uses this)
- Review yield across all projects: `~/.claude/agentic-loop/telemetry/review-yield.jsonl`

The ledger is never committed: `.gitignore` lists `.llm/telemetry/`, and the collector drops a
self-ignoring `.gitignore` (`*`) into the directory.

## Use it during the loop

```bash
T=~/.claude/agentic-loop/hooks/telemetry-report.py
python3 $T mark "Step 6 · Code smells"               # at the start of each step
python3 $T report --step 6 --name "Code smells"      # when the step ends -> chat + telemetry.md
python3 $T findings --step 6 --reviewer smells --total 4 --accepted 1   # after each review fixer
python3 $T summary                                   # before Docs & PR / stop (--json for scripts)
python3 $T yield                                     # which reviewers earn their cost
python3 $T status                                    # sanity check that hooks are firing
```

Run these from the project directory — the reporter resolves the ledger from the cwd.

`report` prints the Stage report block with every measurable field filled and `<fill: …>`
placeholders for judgement fields. Fill those yourself; never ship placeholders.

## Caveats

- `wall_time` from marks includes user-gate waits. Note idle time separately.
- Subagent transcripts are read from the local session directory; a subagent that ran elsewhere
  (cloud) is not counted.
- Cloud / headless runs may not load user hooks — report `n/a (hooks not loaded)`.
- If `status` shows the transcript path is stale, run any prompt once so `SessionStart`
  refreshes `session.json`.
- Token counts are usage, not dollars. `claude -p --output-format json` reports
  `total_cost_usd`; the eval harness records it per run.
