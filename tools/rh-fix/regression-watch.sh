#!/bin/bash
# Regression watch: rebuild our previously-fixed modules at the latest tip.
# Catches reversions like the Bundle0295 #687 -> 743e4c0a regression.
# Usage: regression-watch.sh [repo]
# Exit 0 = all clean, 1 = at least one module fails again.
set -uo pipefail
REPO="${1:-${RH_REPO:-/Volumes/Storage/Riemmann/rh120}}"
BASE="${RH_BASE:-origin/opt/collapse-and-consolidate-4.36}"
LIST="$HOME/.rh-fix/watch-modules.txt"
LOG="$HOME/.rh-fix/regression-watch.log"
cd "$REPO" || exit 2
git fetch -q origin opt/collapse-and-consolidate-4.36 || true
SHA=$(git rev-parse "$BASE")
echo "=== $(date -u '+%F %T UTC') tip=$SHA" | tee -a "$LOG"
failed=0
while IFS= read -r mod; do
  [ -z "$mod" ] && continue
  case "$mod" in \#*) continue ;; esac
  if lake build "$mod" > /tmp/rw-one.log 2>&1; then
    echo "ok   $mod" | tee -a "$LOG"
  else
    echo "FAIL $mod" | tee -a "$LOG"
    grep -E "error: src" /tmp/rw-one.log | head -3 | tee -a "$LOG"
    failed=1
  fi
done < "$LIST"
echo "=== result: $([ "$failed" = 0 ] && echo clean || echo REGRESSED)" | tee -a "$LOG"
exit $failed
