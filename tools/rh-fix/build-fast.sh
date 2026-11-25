#!/bin/bash
# Best-known build flow: cache preflight + optional elabArts-only check.
# Usage: build-fast.sh [--check] [targets...]
#   default targets: Main Challenge
#   --check: build <target>:elabArts (olean+ilean, no IR/C)
set -u
REPO=${RH_REPO:-/work/rh120}
cd "$REPO" || exit 2

MODE=full
TARGETS=()
for a in "$@"; do
  case "$a" in
    --check) MODE=check ;;
    *) TARGETS+=("$a") ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=(Main Challenge)

# shellcheck disable=SC1091
source scripts/cache-env.sh 2>/dev/null || true

echo "== cache preflight =="
lake exe cache get 2>&1 | tail -3 || true

if [ "$MODE" = check ]; then
  BUILD=()
  for t in "${TARGETS[@]}"; do BUILD+=("$t:elabArts"); done
  echo "== elabArts check: ${BUILD[*]} =="
  exec lake build "${BUILD[@]}"
fi

echo "== full build: ${TARGETS[*]} =="
exec lake build "${TARGETS[@]}"
