#!/usr/bin/env python3
"""agentic-loop resumable state in .llm/loop-state.json (runtime, gitignored).

  loop-state.py init --session 20260921-foo [--plan PATH] [--entry full] [--branch B] [--force]
  loop-state.py show [--json]                 where the loop is + what to do next (use to resume)
  loop-state.py step 4 in_progress|done|skipped|blocked [--note TEXT]
  loop-state.py gate plan-review pass|fail|skipped [--note TEXT]
  loop-state.py set [--plan PATH] [--branch B] [--session SLUG]
  loop-state.py bump verify_repairs [--scope 4.5]
                                              exit 3 once the counter exceeds its cap in limits.md
  loop-state.py reset verify_repairs [--scope 4.5] --reason "user granted 2 more tries"
                                              only after the user explicitly approves more attempts
  loop-state.py open add --step 7 --severity MAJOR "summary"
  loop-state.py open close N [--reason TEXT]  close one open finding (or --step 7 for all of a step)
  loop-state.py block "reason"                status=blocked: the loop stops until the user decides
  loop-state.py await "question"              status=awaiting_user (a normal user gate)
  loop-state.py done                          status=done
  loop-state.py limits                        print the caps in effect

The model never edits the JSON by hand: every change goes through this script (atomic writes,
schema kept intact), and caps are enforced by exit codes, not by memory.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    STEP_NAMES, STEP_ORDER, append_ledger_event, git, llm_dir, load_limits, now_iso, project_root,
    read_json, tree_fingerprint, write_json,
)

EXIT_LIMIT = 3
STEP_STATUSES = ("in_progress", "done", "skipped", "blocked")
GATE_STATUSES = ("pass", "fail", "skipped")


def state_path(root: Path) -> Path:
    return llm_dir(root) / "loop-state.json"


def load(root: Path) -> dict:
    st = read_json(state_path(root))
    if not isinstance(st, dict):
        sys.exit("no .llm/loop-state.json - run `loop-state.py init --session <slug>` first")
    return st


def save(root: Path, st: dict) -> None:
    st["updated"] = now_iso()
    st["gates_passed"] = sorted(k for k, v in st.get("gates", {}).items() if v.get("status") == "pass")
    write_json(state_path(root), st)


def next_step(st: dict) -> str | None:
    finished = [s for s, v in st.get("steps", {}).items() if v.get("status") in ("done", "skipped")]
    if not finished:
        return st.get("current_step") or "0"
    last = max(finished, key=lambda s: STEP_ORDER.index(s) if s in STEP_ORDER else -2)
    cur = st.get("current_step")
    if cur and st["steps"].get(cur, {}).get("status") in ("in_progress", "blocked"):
        return cur
    i = STEP_ORDER.index(last) if last in STEP_ORDER else -1
    return STEP_ORDER[i + 1] if i + 1 < len(STEP_ORDER) else None


def cmd_init(args, root: Path) -> int:
    path = state_path(root)
    if path.exists() and not args.force:
        old = read_json(path, {})
        if old.get("status") != "done":
            print(f"refusing: unfinished loop state exists (session {old.get('session')}, "
                  f"step {old.get('current_step')}, status {old.get('status')}). "
                  f"Resume it (`show`) or pass --force to archive it and start fresh.", file=sys.stderr)
            return 1
    if path.exists():
        archived = path.with_name(f"loop-state.{now_iso().replace(':', '')}.json")
        path.rename(archived)
        print(f"archived previous state -> {archived.relative_to(root)}")
    st = {
        "schema": 1,
        "session": args.session,
        "session_dir": f"docs/agentic/{args.session}",
        "plan": args.plan,
        "branch": args.branch or git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "entry": args.entry,
        "status": "in_progress",
        "current_step": None,
        "steps": {},
        "gates": {},
        "gates_passed": [],
        "verify": None,
        "counters": {},
        "limits": load_limits(),
        "open_findings": [],
        "blocked_reason": None,
        "created": now_iso(),
    }
    save(root, st)
    print(f"initialised {path.relative_to(root)} (session {args.session}, entry {args.entry})")
    return 0


def cmd_show(args, root: Path) -> int:
    st = load(root)
    if args.json:
        print(json.dumps(st, indent=2, ensure_ascii=False))
        return 0
    nxt = next_step(st)
    print(f"session      : {st.get('session')}  ({st.get('session_dir')})")
    print(f"plan         : {st.get('plan') or '-'}")
    head_branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch_note = "" if head_branch == st.get("branch") else f"  !! checked out: {head_branch}"
    print(f"branch       : {st.get('branch')}{branch_note}")
    print(f"entry/status : {st.get('entry')} / {st.get('status')}"
          + (f" - {st['blocked_reason']}" if st.get("blocked_reason") else ""))
    print("steps        : " + ", ".join(f"{s}:{v.get('status')}" for s, v in
                                         sorted(st.get("steps", {}).items(),
                                                key=lambda kv: STEP_ORDER.index(kv[0]) if kv[0] in STEP_ORDER else -2)))
    print(f"gates passed : {', '.join(st.get('gates_passed') or []) or '-'}")
    v = st.get("verify") or {}
    if v:
        cfg = read_json(llm_dir(root) / "verify.json", {}) or {}
        fresh = tree_fingerprint(root, cfg.get("fingerprint_exclude")) == v.get("fingerprint")
        print(f"verify       : {v.get('status')} at {v.get('at')}"
              + ("" if fresh else "  (stale: code changed since - re-run the gate)"))
    else:
        print("verify       : never run")
    counters = st.get("counters", {})
    if counters:
        lim = st.get("limits", {})
        print("counters     : " + "; ".join(
            f"{k}[{sc}]={n}/{lim.get(k, '?')}" for k, scopes in counters.items() for sc, n in scopes.items()))
    opened = [f for f in st.get("open_findings", []) if f.get("status") == "open"]
    print(f"open findings: {len(opened)}")
    for f in opened:
        print(f"  #{f['n']} [step {f['step']}] {f['severity']}: {f['summary']}")
    if st.get("status") == "done":
        print("next         : loop finished")
    else:
        print(f"next         : Step {nxt} · {STEP_NAMES.get(nxt, '?')}"
              + ("  (re-run `verify-gate.py check` first)" if nxt in ("5", "6", "7", "8", "9") else ""))
    return 0


def cmd_step(args, root: Path) -> int:
    if args.id not in STEP_ORDER:
        sys.exit(f"unknown step {args.id!r}; expected one of {STEP_ORDER}")
    st = load(root)
    entry = st.setdefault("steps", {}).setdefault(args.id, {})
    entry["status"] = args.status
    entry["at"] = now_iso()
    if args.note:
        entry["note"] = args.note
    st["current_step"] = args.id
    if args.status == "blocked":
        st["status"] = "blocked"
    elif st.get("status") in ("blocked", "awaiting_user"):
        st["status"] = "in_progress"
        st["blocked_reason"] = None
    save(root, st)
    print(f"step {args.id} · {STEP_NAMES[args.id]} -> {args.status}")
    return 0


def cmd_gate(args, root: Path) -> int:
    st = load(root)
    st.setdefault("gates", {})[args.name] = {"status": args.status, "at": now_iso(),
                                            **({"note": args.note} if args.note else {})}
    save(root, st)
    print(f"gate {args.name} -> {args.status}")
    return 0


def cmd_bump(args, root: Path) -> int:
    st = load(root)
    limit = st.get("limits", {}).get(args.counter)
    if limit is None:
        limit = load_limits().get(args.counter)
    if limit is None:
        sys.exit(f"unknown counter {args.counter!r}; see limits.md")
    scope = args.scope or "loop"
    scopes = st.setdefault("counters", {}).setdefault(args.counter, {})
    scopes[scope] = scopes.get(scope, 0) + 1
    n = scopes[scope]
    save(root, st)
    if n > limit:
        append_ledger_event(root, {"type": "limit_hit", "counter": args.counter, "scope": scope,
                                   "value": n, "limit": limit})
        print(f"LIMIT HIT: {args.counter}[{scope}] = {n} > {limit}. Stop and escalate to the user "
              f"(`loop-state.py block ...`).")
        return EXIT_LIMIT
    print(f"{args.counter}[{scope}] = {n}/{limit}")
    return 0


def cmd_reset(args, root: Path) -> int:
    st = load(root)
    scope = args.scope or "loop"
    scopes = st.setdefault("counters", {}).setdefault(args.counter, {})
    old = scopes.get(scope, 0)
    scopes[scope] = 0
    st.setdefault("resets", []).append({"counter": args.counter, "scope": scope, "from": old,
                                        "reason": args.reason, "at": now_iso()})
    save(root, st)
    append_ledger_event(root, {"type": "limit_reset", "counter": args.counter, "scope": scope, "from": old})
    print(f"{args.counter}[{scope}] reset from {old} (reason: {args.reason})")
    return 0


def cmd_set(args, root: Path) -> int:
    st = load(root)
    changed = []
    for key in ("plan", "branch"):
        val = getattr(args, key)
        if val:
            st[key] = val
            changed.append(f"{key}={val}")
    if args.session:
        st["session"] = args.session
        st["session_dir"] = f"docs/agentic/{args.session}"
        changed.append(f"session={args.session}")
    if not changed:
        sys.exit("nothing to set (use --plan / --branch / --session)")
    save(root, st)
    print("set " + ", ".join(changed))
    return 0


def cmd_open(args, root: Path) -> int:
    st = load(root)
    items = st.setdefault("open_findings", [])
    if args.action == "add":
        if not args.text:
            sys.exit("open add needs a summary")
        n = max([f["n"] for f in items] or [0]) + 1
        items.append({"n": n, "step": args.step, "severity": args.severity or "MAJOR",
                      "summary": args.text, "status": "open", "at": now_iso()})
        save(root, st)
        print(f"open finding #{n} recorded")
        return 0
    closed = 0
    for f in items:
        if f.get("status") != "open":
            continue
        if (args.text and str(f["n"]) == args.text) or (args.step and f["step"] == args.step and not args.text):
            f["status"] = "closed"
            f["closed_at"] = now_iso()
            if args.reason:
                f["reason"] = args.reason
            closed += 1
    save(root, st)
    print(f"closed {closed} finding(s)")
    return 0 if closed else 1


def _set_status(root: Path, status: str, reason: str | None) -> None:
    st = load(root)
    st["status"] = status
    st["blocked_reason"] = reason
    save(root, st)


def cmd_block(args, root: Path) -> int:
    _set_status(root, "blocked", args.reason)
    print(f"blocked: {args.reason}")
    return 0


def cmd_await(args, root: Path) -> int:
    _set_status(root, "awaiting_user", args.reason)
    print(f"awaiting user: {args.reason}")
    return 0


def cmd_done(args, root: Path) -> int:
    _set_status(root, "done", None)
    print("loop marked done")
    return 0


def cmd_limits(args, root: Path) -> int:
    st = read_json(state_path(root))
    lim = (st or {}).get("limits") or load_limits()
    for k, v in lim.items():
        print(f"{k} = {v}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="loop-state.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", help="project root (default: git toplevel of cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--session", required=True, help="yyyymmdd-<slug>")
    p.add_argument("--plan")
    p.add_argument("--entry", default="full")
    p.add_argument("--branch")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("show")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("step")
    p.add_argument("id")
    p.add_argument("status", choices=STEP_STATUSES)
    p.add_argument("--note")
    p.set_defaults(fn=cmd_step)

    p = sub.add_parser("gate")
    p.add_argument("name")
    p.add_argument("status", choices=GATE_STATUSES)
    p.add_argument("--note")
    p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("bump")
    p.add_argument("counter")
    p.add_argument("--scope", help="e.g. the step (4.5) or task (task-3) the counter applies to")
    p.set_defaults(fn=cmd_bump)

    p = sub.add_parser("reset")
    p.add_argument("counter")
    p.add_argument("--scope")
    p.add_argument("--reason", required=True, help="the user's explicit approval, quoted")
    p.set_defaults(fn=cmd_reset)

    p = sub.add_parser("set")
    p.add_argument("--plan")
    p.add_argument("--branch")
    p.add_argument("--session")
    p.set_defaults(fn=cmd_set)

    p = sub.add_parser("open")
    p.add_argument("action", choices=("add", "close"))
    p.add_argument("text", nargs="?", help="summary (add) or finding number (close)")
    p.add_argument("--step")
    p.add_argument("--severity", choices=("CRITICAL", "MAJOR", "MINOR", "NIT"))
    p.add_argument("--reason")
    p.set_defaults(fn=cmd_open)

    p = sub.add_parser("block")
    p.add_argument("reason")
    p.set_defaults(fn=cmd_block)
    p = sub.add_parser("await")
    p.add_argument("reason")
    p.set_defaults(fn=cmd_await)
    sub.add_parser("done").set_defaults(fn=cmd_done)
    sub.add_parser("limits").set_defaults(fn=cmd_limits)

    args = ap.parse_args()
    root = project_root(Path(args.root) if args.root else None)
    return args.fn(args, root)


if __name__ == "__main__":
    sys.exit(main())
