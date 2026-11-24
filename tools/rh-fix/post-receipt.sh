#!/bin/bash
# Run preflight and post its receipt to a PR once (marker-deduped).
# Usage: post-receipt.sh <module> <pr> [gh-repo]
# Env: RH_REPO (checkout), DRY=1 to print instead of posting.
set -u
MOD=${1:?module}
PR=${2:?pr number}
GH_REPO=${3:-rohanarun/riemann-hypothesis}
REPO=${RH_REPO:-/Volumes/Storage/Riemmann/rh120}
SHA=$(git -C "$REPO" rev-parse HEAD)
MARK="<!-- receipt:$MOD:$SHA -->"

if gh api "repos/$GH_REPO/issues/$PR/comments" --paginate --jq '.[].body' 2>/dev/null | grep -qF "$MARK"; then
  echo "receipt already posted for $MOD at $SHA"
  exit 0
fi

OUT=$(RH_REPO="$REPO" "$HOME/.rh-fix/preflight.sh" "$MOD" 2>&1)
echo "$OUT" | tail -4
REC=$(echo "$OUT" | sed -n 's/^receipt: //p' | tail -1)
if [ -z "${REC:-}" ] || [ ! -f "$REC" ]; then
  echo "preflight failed; not posting"
  exit 1
fi

BODY="$MARK
$(cat "$REC")"
if [ "${DRY:-0}" = "1" ]; then
  printf '%s\n' "$BODY" | head -30
else
  gh pr comment "$PR" --repo "$GH_REPO" --body "$BODY" | tail -1
fi
