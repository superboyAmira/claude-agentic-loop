#!/usr/bin/env bash
# Pull your locally-installed copy (~/.claude/skills, ~/.claude/agents,
# ~/.claude/agentic-loop/hooks) back into this repo, so edits you made while
# testing an installed skill/agent get published instead of lost.
#
# Mirror of the Cursor original's sync-from-local.sh. No path rewriting is
# needed here (unlike the Cursor version): every reference in these skill
# files is already the absolute ~/.claude/... path, so the file content is
# identical whether it lives in ~/.claude or in this repo.
#
#   ./sync-from-local.sh              # stage changes, show diff, ask before commit
#   ./sync-from-local.sh --commit "msg"   # stage + commit with this message
#   ./sync-from-local.sh --commit "msg" --push   # also push to origin
#   ./sync-from-local.sh --dry-run    # show what would change, touch nothing
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SRC_SKILLS="$CLAUDE_HOME/skills"
SRC_AGENTS="$CLAUDE_HOME/agents"
SRC_HOOKS="$CLAUDE_HOME/agentic-loop/hooks"

DRY_RUN=0
COMMIT_MSG=""
DO_PUSH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --commit) COMMIT_MSG="${2:-}"; shift 2 ;;
    --push) DO_PUSH=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
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
HOOK_FILES=(
  telemetry-collect.sh
  telemetry-collect.py
  telemetry-report.py
  merge-hooks.py
  _ledger.py
  hooks.template.json
)

RSYNC_FLAGS=(-a -c --delete)
[[ "$DRY_RUN" -eq 1 ]] && RSYNC_FLAGS+=(--dry-run -i)

echo "→ pulling installed copy from $CLAUDE_HOME"

missing=0
for name in "${SKILLS[@]}"; do
  if [[ ! -d "$SRC_SKILLS/$name" ]]; then
    echo "  ! not installed, skipping: skills/$name" >&2
    missing=1
    continue
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    out="$(rsync "${RSYNC_FLAGS[@]}" "$SRC_SKILLS/$name/" "$ROOT/skills/$name/" | grep -v '/$' || true)"
    [[ -n "$out" ]] && echo "$out" | sed "s|^|  would update: skills/$name/|"
  else
    rsync "${RSYNC_FLAGS[@]}" "$SRC_SKILLS/$name/" "$ROOT/skills/$name/" >/dev/null
  fi
done

for name in "${AGENTS[@]}"; do
  if [[ ! -f "$SRC_AGENTS/$name.md" ]]; then
    echo "  ! not installed, skipping: agents/$name.md" >&2
    missing=1
    continue
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    diff -q "$SRC_AGENTS/$name.md" "$ROOT/agents/$name.md" >/dev/null 2>&1 || echo "  would update: agents/$name.md"
  else
    cp "$SRC_AGENTS/$name.md" "$ROOT/agents/$name.md"
  fi
done

for f in "${HOOK_FILES[@]}"; do
  if [[ ! -f "$SRC_HOOKS/$f" ]]; then
    echo "  ! not installed, skipping: hooks/$f" >&2
    missing=1
    continue
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    diff -q "$SRC_HOOKS/$f" "$ROOT/hooks/$f" >/dev/null 2>&1 || echo "  would update: hooks/$f"
  else
    cp "$SRC_HOOKS/$f" "$ROOT/hooks/$f"
  fi
done

if [[ "$missing" -eq 1 ]]; then
  echo "  (some pieces aren't installed locally — run ./install.sh first if that's unexpected)" >&2
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "→ dry run only, nothing written"
  exit 0
fi

cd "$ROOT"
CHANGED="$(git status --porcelain -- skills agents hooks)"
if [[ -z "$CHANGED" ]]; then
  echo "→ no changes — installed copy already matches the repo"
  exit 0
fi

echo
echo "→ changes pulled in:"
echo "$CHANGED"

git add skills agents hooks

echo
echo "→ diff summary:"
git --no-pager diff --cached --stat -- skills agents hooks

if [[ -z "$COMMIT_MSG" ]]; then
  echo
  echo "Staged but not committed. Review with 'git diff --cached', then:"
  echo "  git commit -m 'your message'"
  echo "  git push"
  exit 0
fi

git commit -m "$COMMIT_MSG"
echo "→ committed: $COMMIT_MSG"

if [[ "$DO_PUSH" -eq 1 ]]; then
  git push
  echo "→ pushed to $(git remote get-url origin)"
else
  echo "→ not pushed. Run: git push"
fi
