#!/usr/bin/env python3
"""agentic-loop telemetry reporter.

  telemetry-report.py mark "Step 6 · Code smells"
  telemetry-report.py report --step 6 --name "Code smells"
  telemetry-report.py findings --step 5 --reviewer quality --total 6 --accepted 2 --rejected 4
  telemetry-report.py yield [--project NAME] [--include-evals]
  telemetry-report.py summary [--json]
  telemetry-report.py status

Reads the transcript JSONL that the SessionStart hook recorded in <ledger>/session.json,
plus the subagent transcripts next to it (<session>/subagents/agent-*.jsonl), and sums
`message.usage` per assistant message between marks.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "bin"))
from _ledger import ensure_dir, resolve_dir, yield_path  # noqa: E402

FILE_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "create_file", "str_replace"}
STEP_IN_LABEL = re.compile(r"Step\s+(-?[\d.]+)", re.IGNORECASE)


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


def fmt_k(n):
    return f"{n / 1000:.0f}k" if n >= 10000 else f"{n:,}"


def context_warn_tokens():
    try:
        from _common import load_limits  # bin/_common.py
        return load_limits().get("context_warn_tokens")
    except (ImportError, SystemExit):
        return None


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


def all_transcripts(events, sess_path):
    """Every transcript the hooks have seen for this project, oldest first.

    A loop that is resumed in a new session spans several transcripts; session.json only
    remembers the latest one, but every hook event carries its transcript_path.
    """
    seen = []
    for e in events:
        tp = e.get("transcript_path")
        if tp and tp not in seen:
            seen.append(tp)
    latest, _ = load_transcript(sess_path)
    if latest is not None and str(latest) not in seen:
        seen.append(str(latest))
    return [p for p in (Path(t).expanduser() for t in seen) if p.exists()]


def _rows(path):
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") == "assistant":
            yield row


def _in_window(ts, since, until):
    if ts is None:
        return True
    if since and ts < since:
        return False
    if until and ts > until:
        return False
    return True


def _prompt_size(usage):
    return ((usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0))


def _usage_by_message(path, since, until):
    """{message_id: (ts, usage, model)} for assistant messages in the window.

    The transcript writes one row per content block and every row repeats the message's
    full usage, so rows must be collapsed per message id before summing.
    """
    msgs = {}
    for i, row in enumerate(_rows(path)):
        ts = iso_to_epoch(row.get("timestamp"))
        if not _in_window(ts, since, until):
            continue
        msg = row.get("message") or {}
        usage = msg.get("usage") or {}
        mid = msg.get("id") or f"row-{i}"
        prev = msgs.get(mid)
        if prev is None or (usage.get("output_tokens") or 0) >= (prev[1].get("output_tokens") or 0):
            msgs[mid] = (ts if ts is not None else (prev[0] if prev else None), usage, msg.get("model"))
    return msgs


def scan_transcript(tp, since_epoch, until_epoch=None):
    """Sum usage + tool calls for the parent's assistant messages in (since, until]."""
    agg = {
        "in": 0, "out": 0, "cache_read": 0, "cache_write": 0,
        "turns": 0, "models": set(), "tools": {}, "files": set(),
        "subagents": [], "first_ts": None, "last_ts": None,
        "context_last": None, "context_peak": 0, "model_counts": {},
    }
    msgs = _usage_by_message(tp, since_epoch, until_epoch)
    last_ts = None
    for ts, usage, model in msgs.values():
        if ts is not None:
            agg["first_ts"] = ts if agg["first_ts"] is None else min(agg["first_ts"], ts)
            agg["last_ts"] = ts if agg["last_ts"] is None else max(agg["last_ts"], ts)
        if usage:
            agg["turns"] += 1
            agg["in"] += usage.get("input_tokens", 0) or 0
            agg["out"] += usage.get("output_tokens", 0) or 0
            agg["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
            agg["cache_write"] += usage.get("cache_creation_input_tokens", 0) or 0
            size = _prompt_size(usage)
            agg["context_peak"] = max(agg["context_peak"], size)
            if ts is not None and (last_ts is None or ts >= last_ts):
                last_ts, agg["context_last"] = ts, size
        if model and model != "<synthetic>":
            agg["models"].add(model)
            agg["model_counts"][model] = agg["model_counts"].get(model, 0) + 1

    for row in _rows(tp):
        if not _in_window(iso_to_epoch(row.get("timestamp")), since_epoch, until_epoch):
            continue
        for block in (row.get("message") or {}).get("content", []) or []:
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


def scan_subagents(tp, since_epoch, until_epoch=None):
    """Token totals per subagent type from <transcript stem>/subagents/agent-*.jsonl."""
    out = {"agents": 0, "in": 0, "out": 0, "models": set(), "by_type": {}}
    sub_dir = tp.with_suffix("") / "subagents"
    if not sub_dir.is_dir():
        return out
    for f in sorted(sub_dir.glob("agent-*.jsonl")):
        msgs = _usage_by_message(f, since_epoch, until_epoch)
        if not msgs:
            continue
        meta = {}
        try:
            meta = json.loads(f.with_name(f.stem + ".meta.json").read_text())
        except (OSError, ValueError):
            pass
        kind = meta.get("agentType") or "subagent"
        t_in = sum(_prompt_size(u) for _, u, _ in msgs.values())
        t_out = sum((u.get("output_tokens") or 0) for _, u, _ in msgs.values())
        models = {m for _, _, m in msgs.values() if m}
        slot = out["by_type"].setdefault(kind, {"agents": 0, "in": 0, "out": 0})
        slot["agents"] += 1
        slot["in"] += t_in
        slot["out"] += t_out
        out["agents"] += 1
        out["in"] += t_in
        out["out"] += t_out
        out["models"] |= models
    return out


def scan_all(tps, since_epoch, until_epoch=None):
    """scan_transcript + scan_subagents over several transcripts, merged."""
    agg = scan_transcript(tps[0], since_epoch, until_epoch)
    sub = scan_subagents(tps[0], since_epoch, until_epoch)
    for tp in tps[1:]:
        a = scan_transcript(tp, since_epoch, until_epoch)
        for k in ("in", "out", "cache_read", "cache_write", "turns"):
            agg[k] += a[k]
        agg["models"] |= a["models"]
        for name, n in a["model_counts"].items():
            agg["model_counts"][name] = agg["model_counts"].get(name, 0) + n
        agg["files"] |= a["files"]
        agg["subagents"] += a["subagents"]
        for name, n in a["tools"].items():
            agg["tools"][name] = agg["tools"].get(name, 0) + n
        agg["context_peak"] = max(agg["context_peak"], a["context_peak"])
        if a["last_ts"] and (agg["last_ts"] is None or a["last_ts"] >= agg["last_ts"]):
            agg["context_last"] = a["context_last"]
        for k, pick in (("first_ts", min), ("last_ts", max)):
            vals = [v for v in (agg[k], a[k]) if v is not None]
            agg[k] = pick(vals) if vals else None
        s = scan_subagents(tp, since_epoch, until_epoch)
        for k in ("agents", "in", "out"):
            sub[k] += s[k]
        sub["models"] |= s["models"]
        for kind, v in s["by_type"].items():
            slot = sub["by_type"].setdefault(kind, {"agents": 0, "in": 0, "out": 0})
            for k in ("agents", "in", "out"):
                slot[k] += v[k]
    return agg, sub


def total_in(agg):
    return agg["in"] + agg["cache_read"] + agg["cache_write"]


def marks(events):
    return [e for e in events if e.get("type") == "mark"]


def events_between(events, kind, since, until=None):
    return [e for e in events if e.get("type") == kind and _in_window(e.get("ts"), since, until)]


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

    tps = all_transcripts(events, sess)
    step = args.step if args.step is not None else "N"
    findings = events_between(events, "findings", start)
    verifies = events_between(events, "verify", start)

    if not tps:
        _print_block(step, label, None, None, start, findings, verifies,
                     note="n/a (transcript not found - run one prompt so SessionStart refreshes session.json)")
        return 0

    agg, sub = scan_all(tps, start)
    _print_block(step, label, agg, sub, start, findings, verifies)
    return 0


def _tokens_line(agg, sub):
    if agg is None or agg["turns"] == 0:
        return "n/a (no assistant turns recorded in window)"
    ti = total_in(agg)
    line = (f"parent in {ti:,} / out {agg['out']:,} (uncached in {agg['in']:,}; cache read "
            f"{agg['cache_read']:,}, write {agg['cache_write']:,}) over {agg['turns']} message(s)")
    if sub and sub["agents"]:
        line += (f"; subagents in {sub['in']:,} / out {sub['out']:,} over {sub['agents']} agent(s); "
                 f"total {ti + agg['out'] + sub['in'] + sub['out']:,}")
    else:
        line += f"; total {ti + agg['out']:,}"
    return line


def _context_line(agg):
    if not agg or not agg.get("context_last"):
        return "n/a (no parent messages in window)"
    line = f"~{fmt_k(agg['context_last'])} tokens in the last parent prompt (peak {fmt_k(agg['context_peak'])})"
    warn = context_warn_tokens()
    if warn and agg["context_last"] > warn:
        line += (f" - over context_warn_tokens={fmt_k(warn)}: recommend /compact or a fresh session "
                 f"+ `/agentic-loop resume`")
    return line


def _findings_line(findings):
    if not findings:
        return None
    tot = sum(f.get("total", 0) for f in findings)
    acc = sum(f.get("accepted", 0) for f in findings)
    rej = sum(f.get("rejected", 0) for f in findings)
    per = {}
    for f in findings:
        slot = per.setdefault(f.get("reviewer", "?"), [0, 0])
        slot[0] += f.get("accepted", 0)
        slot[1] += f.get("total", 0)
    detail = ", ".join(f"{r} {a}/{t}" for r, (a, t) in per.items())
    return f"total {tot} / accepted {acc} / rejected {rej} ({detail})"


def _gate_line(verifies):
    if not verifies:
        return None
    last = verifies[-1]
    reds = sum(1 for v in verifies if v.get("status") != "pass")
    return (f"{last.get('status')} (last run{', failed ' + ','.join(last.get('failed') or []) if last.get('failed') else ''}; "
            f"{len(verifies)} run(s), {reds} red)")


def _print_block(step, name, agg, sub, start, findings, verifies, note=None):
    wall = "n/a"
    if agg and agg["first_ts"] and agg["last_ts"]:
        wall = fmt_dur(agg["last_ts"] - agg["first_ts"])
    elif start:
        wall = fmt_dur(time.time() - start) + " (mark->now)"

    counts = agg["model_counts"] if agg else {}
    parent = max(counts, key=counts.get) if counts else "unknown"
    sub_models = sorted(m for m in sub["models"] if m != "<synthetic>") if sub else []
    agents = sorted(set(agg["subagents"])) if agg else []
    if sub and sub["by_type"]:
        agents = [f"{k} x{v['agents']} ({fmt_k(v['in'] + v['out'])} tok)" for k, v in sorted(sub["by_type"].items())]
    tools = ""
    if agg and agg["tools"]:
        tools = "; ".join(f"{k}x{v}" for k, v in sorted(agg["tools"].items(), key=lambda kv: -kv[1]))
    files = sorted(agg["files"])[:10] if agg else []

    print(f"### Stage report — Step {step} · {name}")
    print("- status: <fill: done | in progress | skipped | blocked>")
    print(f"- model_parent: {parent}")
    print(f"- models_subagents: {sub_models}")
    print(f"- agents_used: {agents}")
    print(f"- tools: {tools or 'n/a'}")
    print(f"- files_touched: {len(files)}" + (f" ({', '.join(files)})" if files else ""))
    print(f"- tokens: {note or _tokens_line(agg, sub)}")
    print(f"- context: {_context_line(agg)}")
    print(f"- wall_time: {wall}")
    gate = _gate_line(verifies)
    if gate:
        print(f"- gate: {gate}")
    fl = _findings_line(findings)
    if fl:
        print(f"- findings: {fl}")
    print("- cost_notes: <fill: mode notes / brief fact>")
    print("- artifacts: <fill: paths written this step>")
    print(f"- next: <fill: Step {step}+1 · Name | concrete next action>")


def cmd_findings(args):
    d, evt, sess = ledger_paths()
    rejected = args.rejected if args.rejected is not None else max(args.total - args.accepted, 0)
    if args.accepted + rejected > args.total:
        print("! accepted + rejected exceeds total", file=sys.stderr)
        return 2
    _, sessinfo = load_transcript(sess)
    event = {
        "type": "findings", "step": str(args.step), "reviewer": args.reviewer,
        "iteration": args.iteration, "total": args.total, "accepted": args.accepted,
        "rejected": rejected, "severe_accepted": args.severe_accepted,
    }
    append_event(evt, dict(event))
    row = dict(event)
    row.update(ts=time.time(), project=Path.cwd().name,
               session_id=(sessinfo or {}).get("session_id"),
               eval=os.environ.get("AGENTIC_LOOP_EVAL") == "1")
    yp = yield_path()
    ensure_dir(yp.parent)
    with yp.open("a") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    print(f"findings step {args.step} {args.reviewer}: {args.accepted}/{args.total} accepted, {rejected} rejected")
    return 0


def cmd_yield(args):
    yp = yield_path()
    rows = read_events(yp)
    rows = [r for r in rows if args.include_evals or not r.get("eval")]
    if args.project:
        rows = [r for r in rows if r.get("project") == args.project]
    if not rows:
        print(f"no findings recorded yet ({yp})")
        return 0
    groups = {}
    for r in rows:
        key = (str(r.get("step")), r.get("reviewer", "?"))
        g = groups.setdefault(key, {"calls": 0, "sessions": set(), "total": 0, "accepted": 0, "severe": 0})
        g["calls"] += 1
        g["sessions"].add(r.get("session_id"))
        g["total"] += r.get("total", 0)
        g["accepted"] += r.get("accepted", 0)
        g["severe"] += r.get("severe_accepted") or 0

    def order(key):
        step = key[0]
        try:
            return (float(step), key[1])
        except ValueError:
            return (99.0, key[1])

    print("### Review yield (accepted findings per reviewer)")
    print("| Step | Reviewer | Runs | Calls | Findings | Accepted | Rate | Accepted/call | CRIT+MAJOR accepted |")
    print("|------|----------|------|-------|----------|----------|------|---------------|---------------------|")
    for key in sorted(groups, key=order):
        g = groups[key]
        rate = f"{100 * g['accepted'] / g['total']:.0f}%" if g["total"] else "n/a"
        print(f"| {key[0]} | {key[1]} | {len(g['sessions'])} | {g['calls']} | {g['total']} | {g['accepted']} | "
              f"{rate} | {g['accepted'] / g['calls']:.2f} | {g['severe']} |")
    print()
    print(f"- source: {yp} ({len(rows)} row(s){', evals included' if args.include_evals else ''})")
    print("- rule of thumb: a reviewer under ~10% acceptance with no CRIT/MAJOR accepted over 15+ runs "
          "is a candidate to cut or re-prompt")
    return 0


def _summary_rows(events, tps):
    ms = marks(events)
    rows = []
    for i, m in enumerate(ms):
        nxt = ms[i + 1]["ts"] if i + 1 < len(ms) else None
        label = m.get("label", "?")
        sm = STEP_IN_LABEL.search(label)
        row = {"step": sm.group(1) if sm else "?", "label": label}
        fnd = events_between(events, "findings", m.get("ts"), nxt)
        row["findings_total"] = sum(f.get("total", 0) for f in fnd)
        row["findings_accepted"] = sum(f.get("accepted", 0) for f in fnd)
        ver = events_between(events, "verify", m.get("ts"), nxt)
        row["verify_runs"] = len(ver)
        row["verify_red"] = sum(1 for v in ver if v.get("status") != "pass")
        if tps:
            agg, sub = scan_all(tps, m.get("ts"), nxt)
            row.update(
                wall_s=(agg["last_ts"] - agg["first_ts"]) if agg["first_ts"] and agg["last_ts"] else None,
                parent_in=total_in(agg), parent_out=agg["out"], messages=agg["turns"],
                sub_agents=sub["agents"], sub_in=sub["in"], sub_out=sub["out"],
                context_peak=agg["context_peak"],
            )
        rows.append(row)
    return rows


def cmd_summary(args):
    d, evt, sess = ledger_paths()
    events = read_events(evt)
    ms = marks(events)
    tps = all_transcripts(events, sess)
    tp = tps[-1] if tps else None
    rows = _summary_rows(events, tps)
    limit_hits = [e for e in events if e.get("type") == "limit_hit"]
    session_wall = (time.time() - ms[0]["ts"]) if ms else None

    if args.json:
        print(json.dumps({"steps": rows, "session_wall_s": session_wall, "limit_hits": limit_hits,
                          "transcripts": len(tps), "tokens_source": "transcript ledger" if tps else None},
                         indent=2))
        return 0

    print("### Loop cost summary")
    print("| Step | Name | Wall | Subagents | Tokens parent in/out | Tokens subagents in/out | Findings acc/total | Gate runs (red) |")
    print("|------|------|------|-----------|----------------------|-------------------------|--------------------|-----------------|")
    if not rows:
        print("| - | (no marks recorded) | n/a | 0 | n/a | n/a | - | - |")
        return 0
    tot = {"pi": 0, "po": 0, "si": 0, "so": 0, "sa": 0, "ft": 0, "fa": 0}
    for r in rows:
        tot["ft"] += r["findings_total"]
        tot["fa"] += r["findings_accepted"]
        fnd = f"{r['findings_accepted']}/{r['findings_total']}" if r["findings_total"] else "-"
        gate = f"{r['verify_runs']} ({r['verify_red']})" if r["verify_runs"] else "-"
        if tp is None:
            print(f"| {r['step']} | {r['label']} | n/a | n/a | n/a | n/a | {fnd} | {gate} |")
            continue
        for k, src in (("pi", "parent_in"), ("po", "parent_out"), ("si", "sub_in"), ("so", "sub_out"),
                       ("sa", "sub_agents")):
            tot[k] += r[src]
        ptok = f"{r['parent_in']:,}/{r['parent_out']:,}" if r["messages"] else "n/a"
        stok = f"{r['sub_in']:,}/{r['sub_out']:,}" if r["sub_agents"] else "-"
        print(f"| {r['step']} | {r['label']} | {fmt_dur(r['wall_s'])} | {r['sub_agents']} | {ptok} | {stok} | {fnd} | {gate} |")
    print(f"| **Σ** | | **{fmt_dur(session_wall)}** | **{tot['sa']}** | **{tot['pi']:,}/{tot['po']:,}** | "
          f"**{tot['si']:,}/{tot['so']:,}** | **{tot['fa']}/{tot['ft']}** | |")
    print()
    print(f"- session_wall: {fmt_dur(session_wall)}")
    print(f"- tokens_total: {tot['pi'] + tot['po'] + tot['si'] + tot['so']:,} (parent + subagents)")
    print(f"- tokens_source: {f'transcript ledger ({len(tps)} session transcript(s))' if tps else 'n/a (not exposed)'}")
    if limit_hits:
        print(f"- limit_hits: " + "; ".join(f"{e['counter']}[{e['scope']}]={e['value']}>{e['limit']}" for e in limit_hits))
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
            print(f"transcript usage: {agg['turns']} message(s), in {ti:,} / out {agg['out']:,}, "
                  f"models {sorted(agg['models'])}")
        else:
            print("transcript usage: no usage blocks found (your build may not record them -> tokens n/a)")
        sub = scan_subagents(tp, None)
        print(f"subagents       : {sub['agents']} transcript(s)"
              + (f", in {sub['in']:,} / out {sub['out']:,}" if sub["agents"] else ""))
    else:
        print("transcript      : not found")
    print(f"sessions seen   : {len(all_transcripts(events, sess))} transcript(s) referenced by hook events")

    claude_home = os.environ.get("CLAUDE_HOME")
    settings = (Path(claude_home).expanduser() if claude_home else Path.home() / ".claude") / "settings.json"
    wired = False
    if settings.exists():
        try:
            hk = json.loads(settings.read_text()).get("hooks", {})
            wired = any("telemetry-collect" in json.dumps(v) for v in hk.values())
        except ValueError:
            pass
    print(f"hooks wired     : {'yes (~/.claude/settings.json)' if wired else 'NO - run install.sh from the repo clone'}")
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
    p = sub.add_parser("findings", help="record one reviewer's yield after the fixer ran")
    p.add_argument("--step", required=True)
    p.add_argument("--reviewer", required=True, help="quality | implementation | testing | documentation | "
                                                     "simplification | smells | external | critical")
    p.add_argument("--total", type=int, required=True, help="findings the reviewer reported")
    p.add_argument("--accepted", type=int, required=True, help="findings the fixer fixed")
    p.add_argument("--rejected", type=int, default=None, help="findings the fixer rejected (default total-accepted)")
    p.add_argument("--iteration", type=int, default=1)
    p.add_argument("--severe-accepted", type=int, default=None, help="accepted CRITICAL+MAJOR findings")
    p.set_defaults(fn=cmd_findings)
    p = sub.add_parser("yield", help="acceptance rate per review step/reviewer across all runs")
    p.add_argument("--project")
    p.add_argument("--include-evals", action="store_true")
    p.set_defaults(fn=cmd_yield)
    p = sub.add_parser("summary")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_summary)
    p = sub.add_parser("status")
    p.set_defaults(fn=cmd_status)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
