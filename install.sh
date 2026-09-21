#!/usr/bin/env bash
# Install claude-agentic-loop skills + agents + scripts + telemetry hooks into
# ~/.claude (user-wide, available in every project).
#
#   ./install.sh              # skills, agents, scripts, hooks
#   ./install.sh --no-hooks   # skip the telemetry hooks
#   ./install.sh --uninstall  # remove everything this installer added
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
DEST_SKILLS="$CLAUDE_HOME/skills"
DEST_AGENTS="$CLAUDE_HOME/agents"
DEST_HOOKS="$CLAUDE_HOME/agentic-loop/hooks"
DEST_BIN="$CLAUDE_HOME/agentic-loop/bin"
WITH_HOOKS=1
DO_UNINSTALL=0

for arg in "$@"; do
  case "$arg" in
    --no-hooks) WITH_HOOKS=0 ;;
    --uninstall) DO_UNINSTALL=1 ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

SKILLS=(
  agentic-loop
  agentic-loop-brainstorm
  agentic-loop-plan-make
  agentic-loop-plan-exec
  agentic-loop-review
  agentic-loop-docs-pr
)
AGENTS=(
  agentic-loop-quality
  agentic-loop-implementation
  agentic-loop-testing
  agentic-loop-documentation
  agentic-loop-simplification
  agentic-loop-fixer
  agentic-loop-external-review
  agentic-loop-plan-review
)

if [[ "$DO_UNINSTALL" -eq 1 ]]; then
  echo "→ removing skills"
  for name in "${SKILLS[@]}"; do rm -rf "${DEST_SKILLS:?}/$name" && echo "  ✓ $name"; done
  echo "→ removing agents"
  for name in "${AGENTS[@]}"; do rm -f "$DEST_AGENTS/$name.md" && echo "  ✓ $name"; done
  if [[ -f "$DEST_HOOKS/merge-hooks.py" ]] && command -v python3 >/dev/null 2>&1; then
    echo "→ unwiring hooks"
    python3 "$DEST_HOOKS/merge-hooks.py" --target "$CLAUDE_HOME/settings.json" --uninstall || true
  fi
  rm -rf "${DEST_HOOKS:?}" "${DEST_BIN:?}" "$CLAUDE_HOME/agentic-loop/VERSION"
  echo "Done. Kept your data: ~/.claude/agentic-loop/{telemetry,evals}/ and project .llm/ files."
  exit 0
fi

if command -v python3 >/dev/null 2>&1; then
  echo "→ model routing check"
  python3 "$ROOT/bin/check-models.py" --root "$ROOT" \
    || echo "  ! model-routing drift (see above) - installing anyway; fix with bin/check-models.py --fix" >&2
fi

mkdir -p "$DEST_SKILLS" "$DEST_AGENTS" "$DEST_HOOKS" "$DEST_BIN"

echo "→ skills → $DEST_SKILLS"
for name in "${SKILLS[@]}"; do
  src="$ROOT/skills/$name"
  [[ -d "$src" ]] || { echo "missing: $src" >&2; exit 1; }
  rm -rf "${DEST_SKILLS:?}/$name"
  cp -R "$src" "$DEST_SKILLS/$name"
  echo "  ✓ $name"
done

echo "→ agents → $DEST_AGENTS"
for name in "${AGENTS[@]}"; do
  src="$ROOT/agents/$name.md"
  [[ -f "$src" ]] || { echo "missing: $src" >&2; exit 1; }
  cp "$src" "$DEST_AGENTS/$name.md"
  echo "  ✓ $name"
done

echo "→ hooks → $DEST_HOOKS"
cp "$ROOT/hooks/telemetry-collect.sh" \
   "$ROOT/hooks/telemetry-collect.py" \
   "$ROOT/hooks/telemetry-report.py" \
   "$ROOT/hooks/merge-hooks.py" \
   "$ROOT/hooks/_ledger.py" \
   "$ROOT/hooks/hooks.template.json" \
   "$DEST_HOOKS/"
chmod +x "$DEST_HOOKS/telemetry-collect.sh" "$DEST_HOOKS"/*.py

echo "→ scripts → $DEST_BIN"
cp "$ROOT/bin/_common.py" \
   "$ROOT/bin/verify-gate.py" \
   "$ROOT/bin/loop-state.py" \
   "$ROOT/bin/check-models.py" \
   "$ROOT/bin/eval.py" \
   "$DEST_BIN/"
chmod +x "$DEST_BIN"/*.py
cp "$ROOT/VERSION" "$CLAUDE_HOME/agentic-loop/VERSION"

if [[ "$WITH_HOOKS" -eq 1 ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "→ hook wiring skipped: python3 not found (collector still copied)" >&2
  else
    python3 "$DEST_HOOKS/merge-hooks.py" \
      --target "$CLAUDE_HOME/settings.json" \
      --command "bash $DEST_HOOKS/telemetry-collect.sh"
    echo "  ✓ telemetry collector active in every project"
  fi
else
  echo "→ hook wiring skipped (--no-hooks). Collector copied to $DEST_HOOKS"
fi

cat <<EOF

Done. In any Claude Code session:

  /agentic-loop              full loop (or: full | from-plan | review-only | pr-only | resume)
  /agentic-loop-brainstorm   step 1 only
  /agentic-loop-plan-make    step 2 only
  /agentic-loop-plan-exec    steps 4-4.5 only
  /agentic-loop-review       steps 5-8 only
  /agentic-loop-docs-pr      step 9 only

Scripts: ~/.claude/agentic-loop/bin/{verify-gate,loop-state,eval}.py

Reload / restart Claude Code if the skills do not appear yet.
EOF
if [[ "$WITH_HOOKS" -eq 1 ]]; then
  echo
  echo "Telemetry check:  python3 $DEST_HOOKS/telemetry-report.py status"
fi
