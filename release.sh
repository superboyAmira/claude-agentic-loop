#!/usr/bin/env bash
# Bump VERSION, prepend a CHANGELOG entry, commit and tag a new release of the
# skill pack. This is the "push a new version to the remote repo" side —
# install.sh on a client machine is the other side (pull + install).
#
#   ./release.sh patch              # 1.0.0 -> 1.0.1, commit + tag, no push
#   ./release.sh minor --push       # 1.0.1 -> 1.1.0, commit + tag + push (incl. tags)
#   ./release.sh 2.0.0              # set an explicit version
#
# Run ./sync-from-local.sh first if you edited the installed copy in ~/.claude.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

BUMP="${1:-}"
PUSH=0
for arg in "$@"; do [[ "$arg" == "--push" ]] && PUSH=1; done

[[ -z "$BUMP" ]] && { sed -n '2,10p' "$0"; exit 1; }

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "! working tree has uncommitted changes outside this script's scope." >&2
  echo "  Commit or stash first (or run ./sync-from-local.sh --commit \"...\")." >&2
  exit 1
fi

CUR="$(cat VERSION 2>/dev/null || echo 0.0.0)"
IFS='.' read -r MAJOR MINOR PATCH <<<"$CUR"

case "$BUMP" in
  major) NEW="$((MAJOR + 1)).0.0" ;;
  minor) NEW="$MAJOR.$((MINOR + 1)).0" ;;
  patch) NEW="$MAJOR.$MINOR.$((PATCH + 1))" ;;
  [0-9]*.[0-9]*.[0-9]*) NEW="$BUMP" ;;
  *) echo "unknown bump: $BUMP (use patch|minor|major|X.Y.Z)" >&2; exit 2 ;;
esac

echo "→ $CUR -> $NEW"
echo "$NEW" > VERSION

LOG_RANGE=""
if git rev-parse -q --verify "v$CUR" >/dev/null 2>&1; then
  LOG_RANGE="v$CUR..HEAD"
fi
CHANGES="$(git log --oneline --no-merges ${LOG_RANGE:+"$LOG_RANGE"} -- skills agents hooks install.sh 2>/dev/null || true)"
[[ -z "$CHANGES" ]] && CHANGES="(no tracked commits since last release)"

TMP="$(mktemp)"
{
  echo "## $NEW — $(date +%Y-%m-%d)"
  echo
  echo "$CHANGES" | sed 's/^/- /'
  echo
  if [[ -f CHANGELOG.md ]]; then
    tail -n +2 CHANGELOG.md 2>/dev/null || true
  fi
} > "$TMP"
{ echo "# Changelog"; echo; cat "$TMP"; } > CHANGELOG.md
rm -f "$TMP"

git add VERSION CHANGELOG.md
git commit -m "Release v$NEW"
git tag "v$NEW"
echo "→ committed + tagged v$NEW"

if [[ "$PUSH" -eq 1 ]]; then
  git push
  git push origin "v$NEW"
  echo "→ pushed commit + tag to $(git remote get-url origin)"
else
  echo "→ not pushed. Run:"
  echo "    git push && git push origin v$NEW"
fi
