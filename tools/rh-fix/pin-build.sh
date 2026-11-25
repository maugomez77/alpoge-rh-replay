#!/bin/bash
# Pin-and-build: wait until the fork branch tip has been unchanged for N
# seconds, check out that exact SHA on a scratch branch, build elabArts only,
# and write a machine-readable receipt (JSON + Markdown).
#
# Motivation: the branch moves ~10 commits every ~10 minutes; multi-hour builds
# otherwise test a tip that is dozens of commits stale before they finish.
# A receipt pins the result to the built SHA and records how far the tip moved.
#
# Usage: pin-build.sh [stable_seconds] [branch]
# Env:   RH_REPO (default /work/rh120), RH_BRANCH, DISK_MIN_GB,
#        RH_LOCAL_PREFIX (default probe/pin), RH_OUT, RH_LOG
# Runs inside the rhreplay container.
set -u
export PATH=/root/.elan/bin:$PATH

REPO=${RH_REPO:-/work/rh120}
STABLE=${1:-600}
BRANCH=${2:-${RH_BRANCH:-opt/collapse-and-consolidate-4.36}}
PREFIX=${RH_LOCAL_PREFIX:-probe/pin}

cd "$REPO" || exit 2

# shellcheck disable=SC1091
source "$(dirname "$0")/disk-guard.sh" 2>/dev/null || true

state() { echo "[pin-build] $*"; }

fetch_tip() {
  git ls-remote origin "refs/heads/$BRANCH" 2>/dev/null | awk 'NR==1{print $1}'
}

df_gb() {
  df -Pk "$1" 2>/dev/null | awk 'NR==2 {printf "%d", $4/1048576}'
}

digest() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

# 1. Quiescence gate: reset the timer whenever the remote tip changes.
state "waiting for $BRANCH to stay unchanged for ${STABLE}s"
last=$(fetch_tip)
[ -z "$last" ] && { state "cannot read remote tip"; exit 4; }
since=$(date +%s)
while :; do
  sleep 60
  tip=$(fetch_tip)
  now=$(date +%s)
  if [ -z "$tip" ]; then
    state "remote tip unreadable; retrying"
    continue
  fi
  if [ "$tip" != "$last" ]; then
    last=$tip
    since=$now
    state "tip moved to ${tip:0:10}; quiescence timer reset"
  elif [ $((now - since)) -ge "$STABLE" ]; then
    break
  fi
done

SHA=$last
SHORT=$(git rev-parse --short=10 "$SHA" 2>/dev/null || echo "${SHA:0:10}")
OUT=${RH_OUT:-$HOME/.rh-fix/pin-$SHORT}
LOG=${RH_LOG:-/work/pinbuild-$SHORT.log}
mkdir -p "$OUT"

state "tip is stable: $SHA"
git fetch origin "$BRANCH" || { state "fetch failed"; exit 5; }
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  state "tracked changes present; refusing to reset the worktree"
  exit 5
fi
git checkout -B "$PREFIX-$SHORT" "$SHA" || { state "checkout failed"; exit 5; }

# 2. Disk guard (VM and, when on the host, macOS too).
if command -v disk_guard >/dev/null 2>&1; then
  disk_guard "${DISK_MIN_GB:-100}" "$REPO" || { state "disk guard refused to build"; exit 3; }
fi

# 3. Build elabArts only (olean/ilean; no 450 GB of IR/C).
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_S=$(date +%s)
DF_BEFORE=$(df_gb "$REPO")
{
  echo "start=$START"
  echo "sha=$SHA"
  echo "branch=$BRANCH"
  echo "mode=elabArts"
  echo "local_branch=$PREFIX-$SHORT"
} > "$LOG"

state "building Main:elabArts Challenge:elabArts -> $LOG"
lake build Main:elabArts Challenge:elabArts >> "$LOG" 2>&1
RC=$?

END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DURATION=$(( $(date +%s) - START_S ))
DF_AFTER=$(df_gb "$REPO")
LAST=$(grep -oE '\[[0-9]+/[0-9]+\]' "$LOG" | tail -1 | tr -d '[]')
DONE=${LAST%%/*}
TOTAL=${LAST##*/}
FIRST_ERR=$(grep -m1 '^error' "$LOG" || true)
LOG_SHA=$(digest "$LOG")

NEWTIP=$(fetch_tip)
BEHIND=""
TIP_END=${NEWTIP:-$SHA}
if [ -n "$NEWTIP" ] && git cat-file -e "$NEWTIP^{commit}" 2>/dev/null; then
  BEHIND=$(git rev-list --count "$SHA..$NEWTIP" 2>/dev/null || echo "")
fi

RB_SHA=$SHA RB_SHORT=$SHORT RB_BRANCH=$BRANCH RB_MODE=elabArts \
RB_START=$START RB_END=$END RB_DURATION=$DURATION RB_EXIT=$RC \
RB_DONE=${DONE:-0} RB_TOTAL=${TOTAL:-0} RB_FIRST_ERR=${FIRST_ERR:-} \
RB_LOG=$LOG RB_LOG_SHA=$LOG_SHA RB_DF_BEFORE=${DF_BEFORE:-0} \
RB_DF_AFTER=${DF_AFTER:-0} RB_TIP_END=$TIP_END RB_BEHIND=${BEHIND:-} \
RB_STABLE=$STABLE RB_LOCAL=$PREFIX-$SHORT \
python3 - "$OUT/receipt.json" <<'PY'
import json, os, sys

def num(name):
    v = os.environ.get(name, "")
    try:
        return int(v)
    except ValueError:
        return None

receipt = {
    "sha": os.environ["RB_SHA"],
    "short": os.environ["RB_SHORT"],
    "branch": os.environ["RB_BRANCH"],
    "local_branch": os.environ.get("RB_LOCAL", ""),
    "mode": os.environ["RB_MODE"],
    "started_utc": os.environ["RB_START"],
    "ended_utc": os.environ["RB_END"],
    "duration_s": num("RB_DURATION"),
    "exit": num("RB_EXIT"),
    "jobs_done": num("RB_DONE"),
    "jobs_total": num("RB_TOTAL"),
    "first_error": os.environ.get("RB_FIRST_ERR") or None,
    "log": os.environ.get("RB_LOG", ""),
    "log_sha256": os.environ.get("RB_LOG_SHA", ""),
    "disk_free_gb_before": num("RB_DF_BEFORE"),
    "disk_free_gb_after": num("RB_DF_AFTER"),
    "tip_at_end": os.environ.get("RB_TIP_END", ""),
    "commits_behind_tip": num("RB_BEHIND"),
    "stable_for_s": num("RB_STABLE"),
}
with open(sys.argv[1], "w") as f:
    json.dump(receipt, f, indent=2, sort_keys=True)
    f.write("\n")
PY

{
  echo "# Pinned build receipt"
  echo
  echo "- SHA: \`$SHA\`"
  echo "- Branch: \`$BRANCH\` (local \`$PREFIX-$SHORT\`)"
  echo "- Mode: elabArts (olean/ilean)"
  echo "- Window: $START -> $END (${DURATION}s)"
  echo "- Exit: $RC"
  echo "- Jobs: ${DONE:-?}/${TOTAL:-?}"
  echo "- First error: ${FIRST_ERR:-none}"
  echo "- Tip at end: \`${TIP_END}\` (${BEHIND:-?} commits ahead)"
  echo "- Disk free: ${DF_BEFORE:-?}G -> ${DF_AFTER:-?}G"
  echo "- Log: \`$LOG\` ($LOG_SHA)"
} > "$OUT/RECEIPT.md"

state "exit=$RC jobs=${DONE:-?}/${TOTAL:-?} behind=${BEHIND:-?} receipt=$OUT/receipt.json"
[ "$RC" -eq 0 ] || state "first error: ${FIRST_ERR:-none}"
exit "$RC"
