#!/bin/bash
# Best-known build flow: cache preflight, disk guard, elabArts by default.
# Usage: build-fast.sh [--check|--ir] [targets...]
#   default targets: Main Challenge
#   default mode: <target>:elabArts (olean+ilean, no IR/C)
#   --check: alias for the default elabArts mode
#   --ir: use default Lake facets (writes .ir/.c; 450 GB on the full tree)
set -u
REPO=${RH_REPO:-/work/rh120}
cd "$REPO" || exit 2

# shellcheck disable=SC1091
source "$(dirname "$0")/disk-guard.sh" 2>/dev/null || true
if command -v disk_guard >/dev/null 2>&1; then
  disk_guard "${DISK_MIN_GB:-100}" "$REPO" || exit 3
fi

MODE=elabArts
TARGETS=()
for a in "$@"; do
  case "$a" in
    --check) MODE=elabArts ;;
    --ir) MODE=ir ;;
    *) TARGETS+=("$a") ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=(Main Challenge)

# shellcheck disable=SC1091
source scripts/cache-env.sh 2>/dev/null || true

echo "== cache preflight =="
lake exe cache get 2>&1 | tail -3 || true

if [ "$MODE" = elabArts ]; then
  BUILD=()
  for t in "${TARGETS[@]}"; do BUILD+=("$t:elabArts"); done
  echo "== elabArts build: ${BUILD[*]} =="
  exec lake build "${BUILD[@]}"
fi

echo "== default-facet (IR) build: ${TARGETS[*]} =="
exec lake build "${TARGETS[@]}"
