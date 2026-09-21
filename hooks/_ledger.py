"""Shared ledger-location logic for the agentic-loop telemetry collector + reporter."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

ROTATE_BYTES = 20 * 1024 * 1024


def resolve_dir(cwd=None):
    """Where the telemetry ledger for this project lives.

    Priority:
      1. $CLAUDE_LOOP_TELEMETRY_DIR
      2. <cwd>/.llm/telemetry   (when <cwd>/.llm exists — Step -1 creates it)
      3. ~/.claude/agentic-loop/telemetry/<hash of cwd>
    """
    env = os.environ.get("CLAUDE_LOOP_TELEMETRY_DIR")
    if env:
        return Path(env).expanduser()

    base = Path(cwd) if cwd else Path.cwd()
    llm = base / ".llm"
    if llm.is_dir():
        return llm / "telemetry"

    h = hashlib.sha1(str(base.resolve()).encode()).hexdigest()[:12]
    name = base.name or "root"
    return Path.home() / ".claude" / "agentic-loop" / "telemetry" / f"{name}-{h}"


def yield_path():
    """User-wide review-yield log: one line per reviewer invocation, across projects and runs."""
    home = os.environ.get("CLAUDE_HOME")
    base = Path(home).expanduser() if home else Path.home() / ".claude"
    return base / "agentic-loop" / "telemetry" / "review-yield.jsonl"


def ensure_dir(d):
    d.mkdir(parents=True, exist_ok=True)
    gi = d / ".gitignore"
    if not gi.exists():
        try:
            gi.write_text("*\n")
        except OSError:
            pass
    return d


def rotate(path):
    try:
        if path.exists() and path.stat().st_size > ROTATE_BYTES:
            path.rename(path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass
