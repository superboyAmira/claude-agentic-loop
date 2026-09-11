#!/usr/bin/env bash
# Claude Code hook entrypoint for agentic-loop telemetry.
# Wired into ~/.claude/settings.json for SessionStart, Stop, SubagentStop,
# PreCompact, SessionEnd. Reads the hook JSON on stdin, appends one scalar-only
# line to the project telemetry ledger, and ALWAYS exits 0 so a broken collector
# can never block the agent.
set +e

HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || true)"

if [ -z "$PY" ]; then
  # No python: swallow stdin, do nothing, do not block.
  cat >/dev/null 2>&1
  exit 0
fi

"$PY" "$HERE/telemetry-collect.py" 2>/dev/null
exit 0
