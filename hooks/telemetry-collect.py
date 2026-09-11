#!/usr/bin/env python3
"""Append one scalar-only line per Claude Code hook event to the project ledger.

Never raises, never prints anything the agent must read, always exits 0.
Whitelists scalar fields only — never prompt text, thinking text, diffs, or tool output.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ledger import ensure_dir, resolve_dir, rotate  # noqa: E402

SCALAR_KEYS = (
    "hook_event_name", "session_id", "source", "reason", "trigger",
    "stop_hook_active", "cwd", "transcript_path", "permission_mode",
)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    cwd = payload.get("cwd")
    try:
        d = ensure_dir(resolve_dir(cwd))
    except OSError:
        return 0

    event = {k: payload[k] for k in SCALAR_KEYS if k in payload}
    event["ts"] = time.time()

    evt_name = payload.get("hook_event_name", "")

    # SessionStart / any event carrying a transcript path: refresh session.json so
    # the reporter can find the live transcript without a hook of its own.
    tp = payload.get("transcript_path")
    if tp:
        try:
            (d / "session.json").write_text(json.dumps({
                "transcript_path": tp,
                "session_id": payload.get("session_id"),
                "cwd": cwd,
                "updated": time.time(),
            }, indent=2))
        except OSError:
            pass

    ledger = d / "events.jsonl"
    rotate(ledger)
    try:
        with ledger.open("a") as fh:
            fh.write(json.dumps(event, separators=(",", ":")) + "\n")
    except OSError:
        pass

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
