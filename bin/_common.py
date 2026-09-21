"""Shared helpers for the agentic-loop bin/ scripts (verify gate, loop state, evals)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
# hooks/ is a sibling of bin/ both in the repo and in ~/.claude/agentic-loop/
sys.path.insert(0, str(HERE.parent / "hooks"))

STEP_ORDER = ["-1", "0", "1", "2", "3", "4", "4.5", "5", "6", "7", "8", "9", "10"]
STEP_NAMES = {
    "-1": "Markup bootstrap", "0": "Index", "1": "Brainstorm", "2": "Plan Make",
    "3": "Plan Review", "4": "Plan Exec", "4.5": "Verify gate", "5": "Agent Review",
    "6": "Code Smells", "7": "External Review", "8": "Critical Review", "9": "Docs & PR",
    "10": "Human Review",
}
DEFAULT_FINGERPRINT_EXCLUDE = [".llm", "docs/agentic", "docs/plans"]


def claude_home() -> Path:
    env = os.environ.get("CLAUDE_HOME")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def git(root: Path, *args: str, binary: bool = False):
    """Run git in root; return stdout (str or bytes) or None on failure."""
    try:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    except OSError:
        return None
    if p.returncode != 0:
        return None
    return p.stdout if binary else p.stdout.decode(errors="replace").strip()


def project_root(start: Path | None = None) -> Path:
    base = (start or Path.cwd()).resolve()
    top = git(base, "rev-parse", "--show-toplevel")
    return Path(top) if top else base


def llm_dir(root: Path) -> Path:
    return root / ".llm"


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    """Atomic write: never leaves a half-written state file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


_WALK_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", "target"}


def _walk_fingerprint(root: Path, exclude) -> str:
    """Outside git: hash path + size + mtime of every file, skipping agent scratch and caches."""
    excluded = {(root / p).resolve() for p in exclude}
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames
                             if d not in _WALK_SKIP and (here / d).resolve() not in excluded)
        for name in sorted(filenames):
            f = here / name
            if f.resolve() in excluded:
                continue
            try:
                st = f.stat()
            except OSError:
                continue
            h.update(f"{f.relative_to(root)}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
    return "fs-" + h.hexdigest()[:13]


def tree_fingerprint(root: Path, exclude=None) -> str:
    """Hash of HEAD + working-tree changes + untracked files, ignoring agent scratch paths.

    Used to tell whether a green verify run still describes the current code. Outside a git
    repo it falls back to a path/size/mtime walk of the tree.
    """
    exclude = DEFAULT_FINGERPRINT_EXCLUDE if exclude is None else exclude
    if git(root, "rev-parse", "--is-inside-work-tree") != "true":
        return _walk_fingerprint(root, exclude)
    spec = ["--", "."] + [f":(exclude){p}" for p in exclude]
    h = hashlib.sha256()
    head = git(root, "rev-parse", "HEAD")
    h.update((head or "no-head").encode())
    diff = git(root, "diff", "HEAD" if head else "--cached", "--binary", *spec, binary=True)
    h.update(diff or b"")
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z", *spec, binary=True) or b""
    for rel in sorted(p for p in untracked.split(b"\0") if p):
        h.update(rel)
        try:
            h.update(hashlib.sha256((root / rel.decode(errors="replace")).read_bytes()).digest())
        except OSError:
            h.update(b"unreadable")
    return h.hexdigest()[:16]


def limits_file() -> Path | None:
    """limits.md is the single source of truth for loop caps (repo layout first, then installed)."""
    rel = Path("skills") / "agentic-loop" / "references" / "limits.md"
    for cand in (HERE.parent / rel, claude_home() / rel):
        if cand.exists():
            return cand
    return None


_LIMIT_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*(\d+)\s*\|")


def load_limits() -> dict:
    """Parse the limits table in limits.md: rows like | `key` | 3 | ... |."""
    path = limits_file()
    if path is None:
        sys.exit("limits.md not found (expected under skills/agentic-loop/references/) - reinstall")
    limits = {}
    for line in path.read_text().splitlines():
        m = _LIMIT_ROW.match(line.strip())
        if m:
            limits[m.group(1)] = int(m.group(2))
    if not limits:
        sys.exit(f"no limits parsed from {path}")
    return limits


def append_ledger_event(root: Path, event: dict) -> None:
    """Best-effort: record an event in the project's telemetry ledger."""
    try:
        from _ledger import ensure_dir, resolve_dir, rotate  # noqa: WPS433
        d = ensure_dir(resolve_dir(root))
        ledger = d / "events.jsonl"
        rotate(ledger)
        event.setdefault("ts", time.time())
        with ledger.open("a") as fh:
            fh.write(json.dumps(event, separators=(",", ":")) + "\n")
    except Exception:  # telemetry must never break the gate
        pass
