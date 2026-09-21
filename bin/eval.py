#!/usr/bin/env python3
"""agentic-loop eval loop: replay recorded tasks, measure, compare skill versions.

  eval.py record --id ID --plan PATH [--base REF] [--acceptance CMD]... [--notes TEXT]
                         (run inside the project after a real loop; stores the case user-locally)
  eval.py list
  eval.py run (--case ID ... | --all) [--label L] [--runner TEMPLATE] [--budget-usd N] [--keep]
  eval.py report [--label L ...]
  eval.py compare LABEL_A LABEL_B

Cases, runs and results live in ~/.claude/agentic-loop/evals/ - never in the skill repo, because
plans and repo paths come from private projects. Each run replays the case's plan in a detached
git worktree at the case's base commit via `/agentic-loop eval <plan>` (non-interactive), then
measures objectively: verify gate, the case's acceptance commands, loop status, review yield,
tokens and cost.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DEFAULT_FINGERPRINT_EXCLUDE, claude_home, git, now_iso, project_root, read_json, write_json,
)

BIN = Path(__file__).resolve().parent
HOOKS = BIN.parent / "hooks"
DEFAULT_RUNNER = ('claude -p "/agentic-loop eval {plan}" --output-format json '
                  '--permission-mode {permission_mode} --permission-prompts none --max-budget-usd {budget_usd}')
DEFAULT_CONFIG = {"runner": DEFAULT_RUNNER, "permission_mode": "auto", "budget_usd": 20, "timeout_s": 7200}


def home() -> Path:
    return claude_home() / "agentic-loop" / "evals"


def config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(read_json(home() / "config.json", {}) or {})
    return cfg


def skill_version() -> str:
    for cand in (BIN.parent / "VERSION", claude_home() / "agentic-loop" / "VERSION"):
        if cand.exists():
            return cand.read_text().strip()
    return "unknown"


def default_branch(root: Path) -> str:
    ref = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref:
        return ref
    for name in ("main", "master", "trunk"):
        if git(root, "rev-parse", "--verify", "-q", name):
            return name
    return "HEAD"


def cmd_record(args) -> int:
    root = project_root()
    plan = (root / args.plan).resolve()
    if not plan.exists():
        sys.exit(f"plan not found: {plan}")
    base = args.base or git(root, "merge-base", "HEAD", default_branch(root))
    base = git(root, "rev-parse", base) if base else None
    if not base:
        sys.exit("could not resolve the base commit; pass --base <sha>")
    case_dir = home() / "cases" / args.id
    if case_dir.exists() and not args.force:
        sys.exit(f"case {args.id} exists; pass --force to overwrite")
    case_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan, case_dir / "plan.md")
    case = {
        "id": args.id, "repo": str(root), "origin": git(root, "remote", "get-url", "origin"),
        "base_ref": base, "plan_name": plan.name, "acceptance": args.acceptance or [],
        "notes": args.notes, "recorded": now_iso(),
    }
    write_json(case_dir / "case.json", case)
    print(f"recorded case {args.id}: base {base[:12]}, plan {plan.name}, "
          f"{len(case['acceptance'])} acceptance command(s) -> {case_dir}")
    return 0


def load_cases(ids=None) -> list:
    cases = []
    for f in sorted((home() / "cases").glob("*/case.json")):
        c = read_json(f)
        if c and (not ids or c["id"] in ids):
            c["_dir"] = str(f.parent)
            cases.append(c)
    return cases


def cmd_list(args) -> int:
    cases = load_cases()
    if not cases:
        print(f"no cases yet - record one with `eval.py record` ({home() / 'cases'})")
        return 0
    for c in cases:
        print(f"{c['id']:<32} base {c['base_ref'][:10]}  plan {c['plan_name']}  "
              f"acceptance {len(c['acceptance'])}  repo {c['repo']}")
    return 0


def _sh(cmd, cwd: Path, env=None, timeout=None):
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, shell=isinstance(cmd, str), capture_output=True,
                           timeout=timeout, executable=shutil.which("bash") if isinstance(cmd, str) else None)
        return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace"), time.monotonic() - t0
    except subprocess.TimeoutExpired:
        return None, "", f"timeout after {timeout}s", time.monotonic() - t0


def _json_out(cmd, cwd: Path, env) -> dict:
    code, out, _, _ = _sh(cmd, cwd, env)
    try:
        return json.loads(out)
    except ValueError:
        return {}


def run_case(case: dict, label: str, cfg: dict, keep: bool) -> dict:
    repo = Path(case["repo"])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = home() / "runs" / f"{case['id']}-{label}-{stamp}"
    wt = run_dir / "worktree"
    run_dir.mkdir(parents=True, exist_ok=True)
    row = {"case": case["id"], "label": label, "skill_version": skill_version(), "ts": now_iso(),
           "run_dir": str(run_dir)}

    if not repo.exists():
        if not case.get("origin"):
            row["error"] = f"repo {repo} missing and no origin recorded"
            return row
        repo = run_dir / "clone"
        code, _, err, _ = _sh(["git", "clone", "--quiet", case["origin"], str(repo)], run_dir)
        if code != 0:
            row["error"] = f"clone failed: {err.strip()[:200]}"
            return row
    code, _, err, _ = _sh(["git", "worktree", "add", "--detach", str(wt), case["base_ref"]], repo)
    if code != 0:
        row["error"] = f"worktree failed: {err.strip()[:200]}"
        return row

    try:
        plan_rel = Path("docs") / "plans" / case["plan_name"]
        (wt / plan_rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(case["_dir"]) / "plan.md", wt / plan_rel)
        env = dict(os.environ, AGENTIC_LOOP_EVAL="1", CLAUDE_LOOP_TELEMETRY_DIR=str(wt / ".llm" / "telemetry"))
        runner = cfg["runner"].format(plan=shlex.quote(str(plan_rel)), permission_mode=cfg["permission_mode"],
                                      budget_usd=cfg["budget_usd"])
        print(f"  $ {runner}")
        code, out, err, wall = _sh(runner, wt, env, timeout=int(cfg["timeout_s"]))
        (run_dir / "runner.out").write_text(out)
        (run_dir / "runner.err").write_text(err)
        row.update(runner_exit=code, wall_s=round(wall, 1))
        try:
            row["cost_usd"] = json.loads(out).get("total_cost_usd")
        except (ValueError, AttributeError):
            row["cost_usd"] = None

        # Objective checks, independent of what the loop claimed.
        vg = [sys.executable, str(BIN / "verify-gate.py"), "--root", str(wt)]
        if not (wt / ".llm" / "verify.json").exists():
            _sh(vg + ["init"], wt, env)
        vcode, vout, _, _ = _sh(vg + ["run", "--label", "eval"], wt, env)
        (run_dir / "verify.json").write_text(vout)
        row["verify_pass"] = {0: True, 1: False}.get(vcode)
        acc = []
        for cmd in case.get("acceptance", []):
            acode, aout, aerr, _ = _sh(cmd, wt, env, timeout=int(cfg["timeout_s"]))
            acc.append(acode == 0)
            (run_dir / f"acceptance-{len(acc)}.log").write_text(aout + aerr)
        row["acceptance_pass"] = all(acc) if acc else None

        state = read_json(wt / ".llm" / "loop-state.json", {}) or {}
        row["loop_status"] = state.get("status")
        row["open_findings"] = sum(1 for f in state.get("open_findings", []) if f.get("status") == "open")
        row["counters"] = state.get("counters", {})
        summ = _json_out([sys.executable, str(HOOKS / "telemetry-report.py"), "summary", "--json"], wt, env)
        steps = summ.get("steps", [])
        row["tokens_parent"] = sum((s.get("parent_in") or 0) + (s.get("parent_out") or 0) for s in steps)
        row["tokens_subagents"] = sum((s.get("sub_in") or 0) + (s.get("sub_out") or 0) for s in steps)
        row["findings_total"] = sum(s.get("findings_total", 0) for s in steps)
        row["findings_accepted"] = sum(s.get("findings_accepted", 0) for s in steps)
        row["verify_red_runs"] = sum(s.get("verify_red", 0) for s in steps)
        row["limit_hits"] = len(summ.get("limit_hits", []))
        status = git(wt, "status", "--porcelain", "--", ".",
                     *[f":(exclude){p}" for p in DEFAULT_FINGERPRINT_EXCLUDE])
        row["files_changed"] = len(status.splitlines()) if status else 0
        write_json(run_dir / "summary.json", summ)
    finally:
        if not keep:
            _sh(["git", "worktree", "remove", "--force", str(wt)], repo)
            if repo == run_dir / "clone":
                shutil.rmtree(repo, ignore_errors=True)
    return row


def cmd_run(args) -> int:
    cfg = config()
    if args.runner:
        cfg["runner"] = args.runner
    if args.budget_usd is not None:
        cfg["budget_usd"] = args.budget_usd
    cases = load_cases(None if args.all else set(args.case or []))
    if not cases:
        sys.exit("no matching cases (see `eval.py list`)")
    label = args.label or skill_version()
    results = home() / "results.jsonl"
    for case in cases:
        print(f"→ {case['id']} [{label}]")
        row = run_case(case, label, cfg, args.keep)
        with results.open("a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  " + json.dumps({k: row.get(k) for k in ("error", "verify_pass", "acceptance_pass", "loop_status",
                                                          "cost_usd", "wall_s")}))
    print(f"results -> {results}")
    return 0


def _agg(rows: list) -> dict:
    def rate(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return (sum(1 for v in vals if v) / len(vals)) if vals else None

    def mean(key):
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return (sum(vals) / len(vals)) if vals else None

    ft = sum(r.get("findings_total") or 0 for r in rows)
    fa = sum(r.get("findings_accepted") or 0 for r in rows)
    return {
        "runs": len(rows),
        # harness failure, or the runner exited non-zero / timed out (runner_exit None)
        "errors": sum(1 for r in rows if r.get("error") or ("runner_exit" in r and r["runner_exit"] != 0)),
        "verify_pass": rate("verify_pass"),
        "acceptance_pass": rate("acceptance_pass"),
        "finished": (sum(1 for r in rows if r.get("loop_status") == "done") / len(rows)) if rows else None,
        "cost_usd": mean("cost_usd"),
        "tokens": mean("tokens_total"),
        "wall_s": mean("wall_s"),
        "finding_acceptance": (fa / ft) if ft else None,
        "open_findings": mean("open_findings"),
    }


def _rows(labels=None) -> list:
    rows = []
    for line in (home() / "results.jsonl").read_text().splitlines() if (home() / "results.jsonl").exists() else []:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        has_tokens = r.get("tokens_parent") is not None or r.get("tokens_subagents") is not None
        r["tokens_total"] = ((r.get("tokens_parent") or 0) + (r.get("tokens_subagents") or 0)) if has_tokens else None
        if not labels or r.get("label") in labels:
            rows.append(r)
    return rows


def _fmt(key, v):
    if v is None:
        return "n/a"
    if key in ("verify_pass", "acceptance_pass", "finished", "finding_acceptance"):
        return f"{100 * v:.0f}%"
    if key == "cost_usd":
        return f"${v:.2f}"
    if key == "tokens":
        return f"{v / 1e6:.1f}M"
    if key == "wall_s":
        return f"{v / 60:.0f}m"
    return f"{v:.1f}" if isinstance(v, float) else str(v)


METRICS = ["runs", "errors", "verify_pass", "acceptance_pass", "finished", "cost_usd", "tokens", "wall_s",
           "finding_acceptance", "open_findings"]


def cmd_report(args) -> int:
    rows = _rows(set(args.label) if args.label else None)
    if not rows:
        print("no results yet")
        return 0
    labels = sorted({r["label"] for r in rows})
    print("| Label | " + " | ".join(METRICS) + " |")
    print("|---" * (len(METRICS) + 1) + "|")
    for label in labels:
        a = _agg([r for r in rows if r["label"] == label])
        print(f"| {label} | " + " | ".join(_fmt(k, a[k]) for k in METRICS) + " |")
    return 0


def cmd_compare(args) -> int:
    rows = _rows({args.a, args.b})
    # Only compare cases both labels ran, so a bigger case set cannot fake an improvement.
    common = {r["case"] for r in rows if r["label"] == args.a} & {r["case"] for r in rows if r["label"] == args.b}
    if not common:
        sys.exit("no case was run under both labels")
    a = _agg([r for r in rows if r["label"] == args.a and r["case"] in common])
    b = _agg([r for r in rows if r["label"] == args.b and r["case"] in common])
    print(f"### {args.a} vs {args.b} on {len(common)} shared case(s)")
    print(f"| Metric | {args.a} | {args.b} |")
    print("|---|---|---|")
    for k in METRICS:
        print(f"| {k} | {_fmt(k, a[k])} | {_fmt(k, b[k])} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="eval.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record")
    p.add_argument("--id", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--base", help="commit the loop started from (default: merge-base with the default branch)")
    p.add_argument("--acceptance", action="append", help="hidden check run after the loop; repeatable")
    p.add_argument("--notes")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_record)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("run")
    p.add_argument("--case", action="append")
    p.add_argument("--all", action="store_true")
    p.add_argument("--label", help="what is being measured, e.g. v1.1.0 or 'reviewer-prompt-b' (default: VERSION)")
    p.add_argument("--runner", help=f"command template (default from config.json): {DEFAULT_RUNNER}")
    p.add_argument("--budget-usd", type=float)
    p.add_argument("--keep", action="store_true", help="keep the worktree for inspection")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("--label", action="append")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("compare")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(fn=cmd_compare)
    args = ap.parse_args()
    if args.cmd == "run" and not (args.all or args.case):
        ap.error("run needs --case ID or --all")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
