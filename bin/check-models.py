#!/usr/bin/env python3
"""Keep model routing in one place: skills/agentic-loop/references/model-routing.md.

model-routing.md holds the role map (role = model) and the agent map (agent -> role).
Everything else refers to roles. This script checks that
  1. every agents/agentic-loop-*.md `model:` line equals the model its role resolves to;
  2. no skill, agent body or README line names a concrete model outside model-routing.md
     (a line carrying `<!-- models-ok -->` is exempt).

  check-models.py              report drift, exit 1 if any
  check-models.py --fix        rewrite the agents' `model:` lines from the role map
  check-models.py --root DIR   repo root or a ~/.claude-style layout (default: repo of this script)
  check-models.py --print      print the resolved role map as JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROUTING = Path("skills") / "agentic-loop" / "references" / "model-routing.md"
MODEL_WORDS = re.compile(r"\b(opus|sonnet|haiku|fable|gemini|grok|codex|gpt-[\w.]+)\b", re.IGNORECASE)
ROLE_LINE = re.compile(r"^([a-z][a-z-]*)\s*=\s*(\S+)")
AGENT_LINE = re.compile(r"^(agentic-loop-[a-z-]+)\s*->\s*([a-z][a-z-]*)")
FM_MODEL = re.compile(r"^model:\s*(\S+)\s*$")
EXEMPT = "<!-- models-ok -->"


def fenced_block(text: str, heading: str) -> list:
    """Lines of the first ``` block after the given '## heading'."""
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip().lower() == heading.lower())
    except StopIteration:
        return []
    out, inside = [], False
    for line in lines[start + 1:]:
        if line.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside:
            out.append(line.split("#", 1)[0].strip())
        elif line.startswith("## "):
            break
    return [l for l in out if l]


def parse_routing(root: Path):
    text = (root / ROUTING).read_text()
    roles = dict(m.groups() for m in map(ROLE_LINE.match, fenced_block(text, "## Role map")) if m)
    agents = dict(m.groups() for m in map(AGENT_LINE.match, fenced_block(text, "## Agent map")) if m)
    return roles, agents


def agent_model_line(path: Path):
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None, lines
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            break
        m = FM_MODEL.match(line)
        if m:
            return i, m.group(1), lines
    return None, None, lines


def scan_mentions(root: Path) -> list:
    files = sorted((root / "skills").glob("agentic-loop*/**/*.md"))
    files += sorted((root / "agents").glob("agentic-loop-*.md"))
    if (root / "README.md").exists():
        files.append(root / "README.md")
    problems = []
    for f in files:
        if f.resolve() == (root / ROUTING).resolve():
            continue
        in_fm = f.parent.name == "agents"
        for n, line in enumerate(f.read_text().splitlines(), start=1):
            if in_fm and n > 1 and line.strip() == "---":
                in_fm = False
                continue
            if in_fm or EXEMPT in line:
                continue
            m = MODEL_WORDS.search(line)
            if m:
                problems.append(f"{f.relative_to(root)}:{n}: names model '{m.group(0)}' - "
                                f"refer to a role from model-routing.md instead")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(prog="check-models.py")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--print", dest="show", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).expanduser().resolve()

    if not (root / ROUTING).exists():
        print(f"! {ROUTING} not found under {root}", file=sys.stderr)
        return 2
    roles, agents = parse_routing(root)
    if args.show:
        print(json.dumps({"roles": roles, "agents": agents}, indent=2))
        return 0

    problems = []
    if not roles or not agents:
        problems.append(f"{ROUTING}: could not parse '## Role map' / '## Agent map' blocks")
    for agent, role in agents.items():
        if role not in roles:
            problems.append(f"{ROUTING}: agent {agent} uses unknown role '{role}'")
            continue
        path = root / "agents" / f"{agent}.md"
        if not path.exists():
            problems.append(f"agents/{agent}.md: missing (listed in the agent map)")
            continue
        idx, current, lines = agent_model_line(path)
        want = roles[role]
        if current == want:
            continue
        if args.fix and idx is not None:
            lines[idx] = f"model: {want}"
            path.write_text("\n".join(lines) + "\n")
            print(f"fixed agents/{agent}.md: model {current} -> {want} (role {role})")
        else:
            problems.append(f"agents/{agent}.md: model is '{current}', role '{role}' resolves to '{want}'"
                            + ("" if idx is not None else " (no model: line in frontmatter)"))
    for path in sorted((root / "agents").glob("agentic-loop-*.md")):
        if path.stem not in agents:
            problems.append(f"agents/{path.name}: not listed in the agent map of {ROUTING}")

    problems += scan_mentions(root)
    for p in problems:
        print(p)
    if problems:
        print(f"\n{len(problems)} model-routing problem(s). Source of truth: {ROUTING}"
              + ("" if args.fix else " (agent `model:` drift is auto-fixable with --fix)"))
        return 1
    print(f"model routing OK: {len(agents)} agents, roles {sorted(roles)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
