#!/bin/bash
# Wait for the in-flight full build to finish, then advance to the latest tip
# and run the delta build in the same warm worktree.
#
# Usage: wait-and-build.sh [old-log] [new-log]
# Runs detached inside the rhreplay container.
set -u
export PATH=/root/.elan/bin:$PATH

REPO=${RH_REPO:-/work/rh120}
OLD_LOG=${1:-/work/mainbuild13.log}
NEW_LOG=${2:-/work/mainbuild14.log}
SUMMARY=${3:-/work/mainbuild13-summary.txt}
BRANCH=${RH_BRANCH:-opt/collapse-and-consolidate-4.36}
LOCAL_BRANCH=${RH_LOCAL:-probe/next}

# 1. wait for the current build (and any lingering workers) to stop
while pgrep -f "lake build Main Challenge" >/dev/null 2>&1; do sleep 30; done
sleep 15

# 2. record the terminal state of the old build
{
  echo "=== old build summary ==="
  date -u
  echo "--- terminal ---"
  tail -3 "$OLD_LOG" 2>/dev/null
  echo "--- error count ---"
  grep -c "^error" "$OLD_LOG" 2>/dev/null || true
  echo "--- failing modules ---"
  grep "^error: src" "$OLD_LOG" 2>/dev/null | sed 's/:[0-9]*:[0-9]*:.*//' | sort -u
  echo "--- terminal marker ---"
  grep -E "^(error: build failed|Build completed)" "$OLD_LOG" 2>/dev/null | tail -2
} > "$SUMMARY" 2>&1

# 3. advance to the latest tip
cd "$REPO" || exit 2
git fetch origin "$BRANCH" || exit 3
TIP=$(git rev-parse FETCH_HEAD)
# only fast-forward or reset the scratch branch; never touch other branches
git checkout -B "$LOCAL_BRANCH" "$TIP" || exit 4
echo "tip=$TIP" | tee -a "$SUMMARY"

# 4. delta build at the tip
{
  echo "=== tip build ==="
  date -u
  echo "tip=$TIP"
  lake build Main Challenge
  rc=$?
  echo "exit=$rc"
  date -u
  exit $rc
} > "$NEW_LOG" 2>&1
