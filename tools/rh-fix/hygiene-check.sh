#!/bin/bash
# Gate: no new global instances versus a baseline census.
#
# Usage:
#   hygiene-check.sh                 full tree vs ~/.rh-fix/instance-census-baseline.json
#   hygiene-check.sh --changed BASE  only files changed since BASE
#   hygiene-check.sh --update        refresh the baseline (after an accepted change)
#
# Exit 0 = no new instances, 1 = gate violation, 2 = setup error.
set -u
export PATH=/root/.elan/bin:$PATH

REPO=${RH_REPO:-/work/rh120}
BASE_JSON="$HOME/.rh-fix/instance-census-baseline.json"
OUT="$HOME/.rh-fix/instance-census"
MODE="full"
CHANGED=""

while [ $# -gt 0 ]; do
  case "$1" in
    --changed) CHANGED="$2"; shift ;;
    --update)  MODE="update" ;;
    --baseline) BASE_JSON="$2"; shift ;;
    *) echo "usage: $0 [--changed BASE] [--update] [--baseline JSON]" >&2; exit 2 ;;
  esac
  shift
done

cd "$REPO" || exit 2
if [ ! -f /work/instance-scan.py ]; then
  echo "error: /work/instance-scan.py missing" >&2
  exit 2
fi

ARGS=(--src src --out "$OUT")
[ -n "$CHANGED" ] && ARGS+=(--changed-only "$CHANGED")

if [ "$MODE" = "update" ]; then
  python3 /work/instance-scan.py "${ARGS[@]}"
  cp "$OUT.json" "$BASE_JSON"
  echo "baseline updated: $BASE_JSON"
  exit 0
fi

if [ ! -f "$BASE_JSON" ]; then
  echo "error: baseline missing at $BASE_JSON (run with --update first)" >&2
  exit 2
fi

python3 /work/instance-scan.py "${ARGS[@]}" --baseline "$BASE_JSON" --gate
