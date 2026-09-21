#!/usr/bin/env python3
"""agentic-loop deterministic verification gate (build / vet / lint / test).

  verify-gate.py init [--force]          detect commands -> .llm/verify.json (committed)
  verify-gate.py run [--label 4.5] [--only build,test]
                                         run them; write .llm/verify/last.json (partial runs:
                                         partial.json) + per-step logs
  verify-gate.py check                   green only if the last run passed AND the tree is unchanged
  verify-gate.py show                    print the config in effect

Exit codes: 0 green, 1 red or stale, 2 not configured / usage error.
stdout is one JSON object meant to be parsed; full logs are in .llm/verify/<step>.log.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DEFAULT_FINGERPRINT_EXCLUDE, append_ledger_event, git, llm_dir, now_iso, project_root,
    read_json, tree_fingerprint, write_json,
)

DEFAULT_TIMEOUT_S = 900
TAIL_LINES = 60
_MAKE_RULE = re.compile(r"^([A-Za-z0-9_./-][A-Za-z0-9_./ -]*?)\s*::?(?![:=])")


def config_path(root: Path) -> Path:
    return llm_dir(root) / "verify.json"


def results_dir(root: Path) -> Path:
    return llm_dir(root) / "verify"


def _node_steps(root: Path) -> list:
    pkg = read_json(root / "package.json", {}) or {}
    scripts = pkg.get("scripts") or {}
    if (root / "pnpm-lock.yaml").exists():
        pm = "pnpm"
    elif (root / "yarn.lock").exists():
        pm = "yarn"
    elif (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        pm = "bun"
    else:
        pm = "npm"
    steps = []
    for name in ("build", "typecheck", "lint", "test"):
        body = scripts.get(name, "")
        if not body or "no test specified" in body:
            continue
        step = {"name": name, "cmd": f"{pm} run {name}"}
        if name == "build":
            step["blocking"] = True
        steps.append(step)
    return steps


def _make_targets(root: Path) -> set:
    mk = root / "Makefile"
    if not mk.exists():
        return set()
    targets = set()
    for line in mk.read_text(errors="replace").splitlines():
        # `name:` or `name::` rules; not `name := value` / `name ::= value` assignments.
        m = _MAKE_RULE.match(line)
        if m:
            targets.update(t for t in m.group(1).split() if not t.startswith("."))
    return targets


def detect(root: Path) -> list:
    """Best-effort command detection. The orchestrator confirms the result with the user."""
    if (root / "go.mod").exists():
        return [
            {"name": "build", "cmd": "go build ./...", "blocking": True},
            {"name": "vet", "cmd": "go vet ./..."},
            {"name": "lint", "cmd": "golangci-lint run", "requires": "golangci-lint", "optional": True},
            {"name": "test", "cmd": "go test ./...", "timeout": 1800},
        ]
    if (root / "Cargo.toml").exists():
        return [
            {"name": "build", "cmd": "cargo build --all-targets", "blocking": True},
            {"name": "lint", "cmd": "cargo clippy --all-targets -- -D warnings",
             "requires": "cargo-clippy", "optional": True},
            {"name": "test", "cmd": "cargo test"},
        ]
    if (root / "package.json").exists():
        steps = _node_steps(root)
        if steps:
            return steps
    if any((root / f).exists() for f in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")):
        steps = [{"name": "lint", "cmd": "ruff check .", "requires": "ruff", "optional": True}]
        if (root / "mypy.ini").exists() or "[tool.mypy]" in (
                (root / "pyproject.toml").read_text(errors="replace") if (root / "pyproject.toml").exists() else ""):
            steps.append({"name": "typecheck", "cmd": "mypy .", "requires": "mypy"})
        steps.append({"name": "test", "cmd": "python3 -m pytest -q"})
        return steps
    targets = _make_targets(root)
    steps = []
    for name in ("build", "lint", "test"):
        if name in targets:
            step = {"name": name, "cmd": f"make {name}"}
            if name == "build":
                step["blocking"] = True
            steps.append(step)
    return steps


def load_config(root: Path):
    cfg = read_json(config_path(root))
    if not isinstance(cfg, dict) or not cfg.get("steps"):
        return None
    return cfg


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        proc.kill()


def run_step(root: Path, step: dict, logdir: Path, default_timeout: int) -> dict:
    name, cmd = step["name"], step["cmd"]
    res = {"name": name, "cmd": cmd}
    req = step.get("requires")
    if req and shutil.which(req) is None:
        res.update(status="skipped" if step.get("optional") else "fail", exit_code=None,
                   duration_s=0.0, reason=f"`{req}` not installed")
        return res

    timeout = int(step.get("timeout", default_timeout))
    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(cmd, shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                executable=shutil.which("bash"), start_new_session=True)
    except OSError as e:
        res.update(status="fail", exit_code=None, duration_s=0.0, reason=f"could not start: {e}")
        return res
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(proc)
        out, _ = proc.communicate()
    text = (out or b"").decode(errors="replace")

    log = logdir / f"{name.replace('/', '_')}.log"
    log.write_text(text)
    code = None if timed_out else proc.returncode
    res.update(status="pass" if code == 0 else "fail", exit_code=code,
               duration_s=round(time.monotonic() - t0, 1), log=str(log.relative_to(root)))
    if code != 0:
        res["reason"] = f"timeout after {timeout}s" if timed_out else f"exit {code}"
        res["tail"] = text.splitlines()[-TAIL_LINES:]
    return res


def _update_loop_state(root: Path, summary: dict, label: str | None) -> None:
    path = llm_dir(root) / "loop-state.json"
    state = read_json(path)
    if not isinstance(state, dict):
        return
    state["verify"] = {k: summary[k] for k in ("status", "at", "fingerprint", "failed")}
    if label:
        state.setdefault("gates", {})[f"verify@{label}"] = {"status": summary["status"], "at": summary["at"]}
        state["gates_passed"] = sorted(k for k, v in state["gates"].items() if v.get("status") == "pass")
    state["updated"] = summary["at"]
    write_json(path, state)


def cmd_init(args, root: Path) -> int:
    path = config_path(root)
    if path.exists() and not args.force:
        print(json.dumps({"config": str(path.relative_to(root)), "created": False, **read_json(path, {})}, indent=2))
        return 0
    steps = detect(root)
    cfg = {
        "schema": 1,
        "timeout_s": DEFAULT_TIMEOUT_S,
        "fingerprint_exclude": DEFAULT_FINGERPRINT_EXCLUDE,
        "steps": steps,
    }
    write_json(path, cfg)
    out = {"config": str(path.relative_to(root)), "created": True, **cfg}
    if not steps:
        out["error"] = "no build/test commands detected: fill `steps` in .llm/verify.json with the user"
        print(json.dumps(out, indent=2))
        return 2
    print(json.dumps(out, indent=2))
    return 0


def cmd_run(args, root: Path) -> int:
    cfg = load_config(root)
    if cfg is None:
        print(json.dumps({"status": "unconfigured",
                          "error": "no steps in .llm/verify.json - run `verify-gate.py init` and confirm with the user"}))
        return 2
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    steps = [s for s in cfg["steps"] if not only or s["name"] in only]
    if not steps:
        print(json.dumps({"status": "unconfigured", "error": f"--only matched no step: {sorted(only or [])}"}))
        return 2

    logdir = results_dir(root)
    logdir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    results, blocked = [], False
    for step in steps:
        if blocked:
            results.append({"name": step["name"], "cmd": step["cmd"], "status": "not_run",
                            "reason": "a blocking step failed earlier"})
            continue
        r = run_step(root, step, logdir, int(cfg.get("timeout_s", DEFAULT_TIMEOUT_S)))
        results.append(r)
        if r["status"] == "fail" and step.get("blocking"):
            blocked = True

    failed = [r["name"] for r in results if r["status"] == "fail"]
    summary = {
        "schema": 1,
        "status": "fail" if failed else "pass",
        "label": args.label,
        "at": now_iso(),
        "head": git(root, "rev-parse", "HEAD"),
        "fingerprint": tree_fingerprint(root, cfg.get("fingerprint_exclude")),
        "partial": bool(only),
        "duration_s": round(time.monotonic() - t0, 1),
        "failed": failed,
        "not_run": [r["name"] for r in results if r["status"] == "not_run"],
        "steps": results,
    }
    # A partial run must not overwrite the last full result that `check` relies on.
    out_file = logdir / ("partial.json" if only else "last.json")
    write_json(out_file, summary)
    append_ledger_event(root, {"type": "verify", "label": args.label, "status": summary["status"],
                               "failed": failed, "duration_s": summary["duration_s"], "partial": bool(only)})
    if not only:
        _update_loop_state(root, summary, args.label)

    brief = {k: summary[k] for k in ("status", "label", "failed", "not_run", "duration_s", "fingerprint")}
    brief["results"] = str(out_file.relative_to(root))
    brief["steps"] = [{k: r.get(k) for k in ("name", "status", "reason", "log") if r.get(k) is not None}
                      for r in results]
    print(json.dumps(brief, indent=2))
    return 0 if summary["status"] == "pass" else 1


def cmd_check(args, root: Path) -> int:
    last = read_json(results_dir(root) / "last.json")
    cfg = load_config(root) or {}
    if not isinstance(last, dict):
        verdict = {"ok": False, "reason": "no verify run recorded"}
    elif last.get("partial"):
        verdict = {"ok": False, "reason": "last run was partial (--only); run the full gate"}
    elif last.get("status") != "pass":
        verdict = {"ok": False, "reason": f"last run is red: {last.get('failed')}"}
    else:
        current = tree_fingerprint(root, cfg.get("fingerprint_exclude"))
        if current is None or current != last.get("fingerprint"):
            verdict = {"ok": False, "reason": "code changed since the last green run (stale)",
                       "last": last.get("fingerprint"), "current": current}
        else:
            verdict = {"ok": True, "at": last.get("at"), "label": last.get("label")}
    print(json.dumps(verdict))
    return 0 if verdict["ok"] else 1


def cmd_show(args, root: Path) -> int:
    cfg = load_config(root)
    if cfg is None:
        print(json.dumps({"configured": False, "detected": detect(root)}, indent=2))
        return 2
    print(json.dumps(cfg, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="verify-gate.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", help="project root (default: git toplevel of cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--force", action="store_true", help="overwrite an existing .llm/verify.json")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("run")
    p.add_argument("--label", help="loop step this run gates, e.g. 4.5 (recorded in loop-state + telemetry)")
    p.add_argument("--only", help="comma-separated step names (partial run -> partial.json; never satisfies `check`)")
    p.set_defaults(fn=cmd_run)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("show").set_defaults(fn=cmd_show)
    args = ap.parse_args()
    root = project_root(Path(args.root) if args.root else None)
    return args.fn(args, root)


if __name__ == "__main__":
    sys.exit(main())
