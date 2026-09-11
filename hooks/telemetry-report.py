#!/usr/bin/env python3
"""agentic-loop telemetry reporter.

  telemetry-report.py mark "Step 6 · Code smells"
  telemetry-report.py report --step 6 --name "Code smells"
  telemetry-report.py summary
  telemetry-report.py status

Reads the transcript JSONL that the SessionStart hook recorded in
<ledger>/session.json and sums `message.usage` per assistant turn between marks.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ledger import ensure_dir, resolve_dir  # noqa: E402

FILE_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "create_file", "str_replace"}


def iso_to_epoch(s):
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def fmt_dur(seconds):
    if seconds is None:
        return "n/a"
    seconds = int(round(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def ledger_paths():
    d = ensure_dir(resolve_dir(None))
    return d, d / "events.jsonl", d / "session.json"


def read_events(evt_path):
    out = []
    if not evt_path.exists():
        return out
    for line in evt_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def append_event(evt_path, obj):
    obj.setdefault("ts", time.time())
    with evt_path.open("a") as fh:
        fh.write(json.dumps(obj, separators=(",", ":")) + "\n")


def load_transcript(sess_path):
    if not sess_path.exists():
        return None, None
    try:
        sess = json.loads(sess_path.read_text())
    except ValueError:
        return None, None
    tp = sess.get("transcript_path")
    if not tp:
        return None, sess
    p = Path(tp).expanduser()
    if not p.exists():
        return None, sess
    return p, sess


def scan_transcript(tp, since_epoch, until_epoch=None):
    """Sum usage + tool calls for assistant turns in (since, until]."""
    agg = {
        "in": 0, "out": 0, "cache_read": 0, "cache_write": 0,
        "turns": 0, "models": set(), "tools": {}, "files": set(),
        "subagents": [], "first_ts": None, "last_ts": None,
    }
    try:
        lines = tp.read_text(errors="replace").splitlines()
    except OSError:
        return agg

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") != "assistant":
            continue
        ts = iso_to_epoch(row.get("timestamp"))
        if ts is not None:
            if since_epoch and ts < since_epoch:
                continue
            if until_epoch and ts > until_epoch:
                continue
            agg["first_ts"] = ts if agg["first_ts"] is None else min(agg["first_ts"], ts)
            agg["last_ts"] = ts if agg["last_ts"] is None else max(agg["last_ts"], ts)

        msg = row.get("message") or {}
        usage = msg.get("usage") or {}
        if usage:
            agg["turns"] += 1
            agg["in"] += usage.get("input_tokens", 0) or 0
            agg["out"] += usage.get("output_tokens", 0) or 0
            agg["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
            agg["cache_write"] += usage.get("cache_creation_input_tokens", 0) or 0
        if msg.get("model"):
            agg["models"].add(msg["model"])

        for block in msg.get("content", []) or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "?")
            agg["tools"][name] = agg["tools"].get(name, 0) + 1
            inp = block.get("input") or {}
            if name in ("Task", "Agent"):
                st = inp.get("subagent_type") or inp.get("description") or "subagent"
                agg["subagents"].append(st)
            if name in FILE_EDIT_TOOLS:
                fp = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
                if fp:
                    agg["files"].add(fp)
    return agg


def total_in(agg):
    return agg["in"] + agg["cache_read"] + agg["cache_write"]


def marks(events):
    return [e for e in events if e.get("type") == "mark"]


def cmd_mark(args):
    d, evt, sess = ledger_paths()
    append_event(evt, {"type": "mark", "label": args.label})
    print(f"marked: {args.label}  (ledger: {d})")
    return 0


def cmd_report(args):
    d, evt, sess = ledger_paths()
    events = read_events(evt)
    ms = marks(events)
    start = None
    label = args.name or ""
    if ms:
        chosen = ms[-1]
        if args.name:
            for m in reversed(ms):
                if args.name.lower() in (m.get("label", "").lower()):
                    chosen = m
                    break
        # 2s grace: a step-start mark can land a hair after the turn it belongs to.
        start = chosen.get("ts")
        if start:
            start -= 2
        label = label or chosen.get("label", "")

    tp, sessinfo = load_transcript(sess)
    step = args.step if args.step is not None else "N"

    if tp is None:
        _print_block(step, label, None, start, note="n/a (transcript not found — run one prompt so SessionStart refreshes session.json)")
        return 0

    agg = scan_transcript(tp, start)
    _print_block(step, label, agg, start)
    return 0


def _tokens_line(agg):
    if agg is None or agg["turns"] == 0:
        return "n/a (no assistant turns recorded in window)"
    ti = total_in(agg)
    return (f"in {ti:,} / out {agg['out']:,} / total {ti + agg['out']:,} "
            f"(uncached in {agg['in']:,}; cache read {agg['cache_read']:,}, "
            f"write {agg['cache_write']:,}) over {agg['turns']} turn(s)")


def _print_block(step, name, agg, start, note=None):
    wall = "n/a"
    if agg and agg["first_ts"] and agg["last_ts"]:
        wall = fmt_dur(agg["last_ts"] - agg["first_ts"])
    elif start:
        wall = fmt_dur(time.time() - start) + " (mark->now)"

    models = sorted(agg["models"]) if agg else []
    parent = models[0] if models else "unknown"
    subs = sorted(set(agg["subagents"])) if agg else []
    tools = ""
    if agg and agg["tools"]:
        tools = "; ".join(f"{k}x{v}" for k, v in sorted(agg["tools"].items(), key=lambda kv: -kv[1]))
    files = sorted(agg["files"])[:10] if agg else []

    print(f"### Stage report — Step {step} · {name}")
    print("- status: <fill: done | in progress | skipped | blocked>")
    print(f"- model_parent: {parent}")
    print(f"- models_subagents: {subs}")
    print(f"- agents_used: {subs}")
    print(f"- tools: {tools or 'n/a'}")
    print(f"- files_touched: {len(files)}" + (f" ({', '.join(files)})" if files else ""))
    print(f"- tokens: {note or _tokens_line(agg)}")
    print("- context: n/a (not exposed to skills in Claude Code)")
    print(f"- wall_time: {wall}")
    print("- cost_notes: <fill: mode notes / brief fact>")
    print("- artifacts: <fill: paths written this step>")
    print(f"- next: <fill: Step {step}+1 · Name | concrete next action>")


def cmd_summary(args):
    d, evt, sess = ledger_paths()
    events = read_events(evt)
    ms = marks(events)
    tp, _ = load_transcript(sess)
    print("### Loop cost summary")
    print("| Step | Name | Wall | Subagents | Tokens in/out/total | Notes |")
    print("|------|------|------|-----------|---------------------|-------|")
    if not ms:
        print("| — | (no marks recorded) | n/a | 0 | n/a | run `telemetry-report.py mark` at each step start |")
        return 0
    bounds = []
    for i, m in enumerate(ms):
        nxt = ms[i + 1]["ts"] if i + 1 < len(ms) else None
        bounds.append((m, nxt))
    tot_in = tot_out = tot_sub = 0
    session_start = ms[0]["ts"]
    for m, nxt in bounds:
        name = m.get("label", "?")
        if tp is None:
            print(f"| ? | {name} | n/a | n/a | n/a | transcript not found |")
            continue
        agg = scan_transcript(tp, m.get("ts"), nxt)
        ti, to = total_in(agg), agg["out"]
        nsub = len(agg["subagents"])
        tot_in += ti
        tot_out += to
        tot_sub += nsub
        wall = fmt_dur((agg["last_ts"] - agg["first_ts"]) if agg["first_ts"] and agg["last_ts"] else None)
        tokcell = f"{ti:,}/{to:,}/{ti + to:,}" if agg["turns"] else "n/a"
        print(f"| ? | {name} | {wall} | {nsub} | {tokcell} | {agg['turns']} turn(s) |")
    print(f"| **Σ** | | **{fmt_dur(time.time() - session_start)}** | **{tot_sub}** | "
          f"**{tot_in:,}/{tot_out:,}/{tot_in + tot_out:,}** | |")
    print()
    print(f"- session_wall: {fmt_dur(time.time() - session_start)}")
    print(f"- tokens_source: {'transcript ledger' if tp else 'n/a (not exposed)'}")
    return 0


def cmd_status(args):
    d, evt, sess = ledger_paths()
    print(f"ledger dir     : {d}")
    print(f"events.jsonl    : {'present' if evt.exists() else 'MISSING'}"
          + (f" ({evt.stat().st_size} bytes)" if evt.exists() else ""))
    events = read_events(evt)
    kinds = {}
    for e in events:
        k = e.get("hook_event_name") or e.get("type") or "?"
        kinds[k] = kinds.get(k, 0) + 1
    print(f"event kinds     : {kinds or '(none)'}")
    print(f"marks recorded  : {len(marks(events))}")

    tp, sessinfo = load_transcript(sess)
    if sessinfo:
        age = time.time() - sessinfo.get("updated", 0)
        print(f"session.json    : present, updated {fmt_dur(age)} ago")
    else:
        print("session.json    : MISSING — SessionStart hook has not fired yet")
    if tp:
        print(f"transcript      : {tp}")
        agg = scan_transcript(tp, None)
        if agg["turns"]:
            ti = total_in(agg)
            print(f"transcript usage: {agg['turns']} turn(s), in {ti:,} / out {agg['out']:,}, "
                  f"models {sorted(agg['models'])}")
        else:
            print("transcript usage: no usage blocks found (your build may not record them -> tokens n/a)")
    else:
        print("transcript      : not found")

    claude_home = os.environ.get("CLAUDE_HOME")
    settings = (Path(claude_home).expanduser() if claude_home else Path.home() / ".claude") / "settings.json"
    wired = False
    if settings.exists():
        try:
            hk = json.loads(settings.read_text()).get("hooks", {})
            wired = any("telemetry-collect" in json.dumps(v) for v in hk.values())
        except ValueError:
            pass
    print(f"hooks wired     : {'yes (~/.claude/settings.json)' if wired else 'NO — run install.sh'}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="telemetry-report.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("mark")
    p.add_argument("label")
    p.set_defaults(fn=cmd_mark)
    p = sub.add_parser("report")
    p.add_argument("--step", type=str, default=None)
    p.add_argument("--name", type=str, default=None)
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("summary")
    p.set_defaults(fn=cmd_summary)
    p = sub.add_parser("status")
    p.set_defaults(fn=cmd_status)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
