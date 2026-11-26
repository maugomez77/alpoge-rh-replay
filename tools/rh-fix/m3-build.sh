#!/bin/bash
# Second builder on the M3 Max (Tailscale / LAN host).
#
# Usage: m3-build.sh <sha> [lake targets...]
#   default targets: Main:elabArts Challenge:elabArts
# Env: RH_REPO (default ~/rh120), RH_BRANCH, DISK_MIN_GB (default 200;
#      set 600 for a full clean-ish build).
set -u
export PATH="$HOME/.elan/bin:$PATH"
export LEAN_ABORT_ON_PANIC=1

REPO=${RH_REPO:-$HOME/rh120}
BRANCH=${RH_BRANCH:-opt/collapse-and-consolidate-4.36}
SHA=${1:?usage: m3-build.sh <sha> [targets...]}
shift || true
TARGETS=("$@")
if [ ${#TARGETS[@]} -eq 0 ]; then
  TARGETS=(Main:elabArts Challenge:elabArts)
fi

git -C "$REPO" fetch origin "$BRANCH" || exit 2
SHORT=$(git -C "$REPO" rev-parse --short=10 "$SHA") || exit 2
git -C "$REPO" checkout -B probe/m3 "$SHA" || exit 2

# shellcheck disable=SC1091
source "$(dirname "$0")/disk-guard.sh" 2>/dev/null || true
if command -v disk_guard >/dev/null 2>&1; then
  disk_guard "${DISK_MIN_GB:-200}" "$REPO" || exit 3
fi

LOG="$HOME/rh-build-$SHORT.log"
cd "$REPO" || exit 2
{
  echo "start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "sha=$SHA"
  echo "targets=${TARGETS[*]}"
} > "$LOG"
lake build "${TARGETS[@]}" >> "$LOG" 2>&1
RC=$?
{
  echo "exit=$RC"
  date -u +%Y-%m-%dT%H:%M:%SZ
} >> "$LOG"
tail -5 "$LOG"
echo "log=$LOG"
exit "$RC"
