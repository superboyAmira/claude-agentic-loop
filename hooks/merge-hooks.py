#!/usr/bin/env python3
"""Merge (or remove) the agentic-loop telemetry hook into ~/.claude/settings.json.

  merge-hooks.py                     # install into ~/.claude/settings.json
  merge-hooks.py --target PATH       # different settings file
  merge-hooks.py --uninstall

Idempotent. Existing hooks are preserved. Our entries are recognised by the
substring 'telemetry-collect' in the command string.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

EVENTS = ["SessionStart", "Stop", "SubagentStop", "PreCompact", "SessionEnd"]
MARKER = "telemetry-collect"
DEFAULT_CMD = "bash ~/.claude/agentic-loop/hooks/telemetry-collect.sh"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except ValueError:
        print(f"! {path} is not valid JSON — refusing to touch it", file=sys.stderr)
        sys.exit(1)


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak-{int(time.time())}"))
    path.write_text(json.dumps(data, indent=2) + "\n")


def has_marker(entry: dict) -> bool:
    return MARKER in json.dumps(entry)


def install(data: dict, cmd: str) -> dict:
    hooks = data.setdefault("hooks", {})
    entry = {"hooks": [{"type": "command", "command": cmd}]}
    for ev in EVENTS:
        arr = hooks.setdefault(ev, [])
        if not any(has_marker(e) for e in arr):
            arr.append(entry)
    return data


def uninstall(data: dict) -> dict:
    hooks = data.get("hooks", {})
    for ev in list(hooks.keys()):
        hooks[ev] = [e for e in hooks[ev] if not has_marker(e)]
        if not hooks[ev]:
            del hooks[ev]
    if "hooks" in data and not data["hooks"]:
        del data["hooks"]
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--command", default=DEFAULT_CMD)
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()

    path = Path(args.target).expanduser()
    data = load(path)

    if args.uninstall:
        data = uninstall(data)
        save(path, data)
        print(f"removed agentic-loop telemetry hooks from {path}")
        return 0

    data = install(data, args.command)
    save(path, data)
    print(f"wired agentic-loop telemetry hooks into {path}")
    print(f"  events: {', '.join(EVENTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
