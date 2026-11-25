#!/bin/bash
# Delta-green build: build only the reverse-dependency closure of what changed.
#
# Usage: delta-build.sh [base] [head]
# Env:   RH_REPO (default /work/rh120), DELTA_MAX (default 15000 modules)
#
# Falls back to `lake build Main Challenge` when the closure is large or a
# config file changed.  Writes a receipt to ~/.rh-fix/delta-<sha>/.
set -u
export PATH=/root/.elan/bin:$PATH

REPO=${RH_REPO:-/work/rh120}
BASE=${1:-origin/opt/collapse-and-consolidate-4.36}
HEAD=${2:-HEAD}
LIMIT=${DELTA_MAX:-15000}

cd "$REPO" || exit 2
SHA=$(git rev-parse "$HEAD") || exit 2
SHORT=$(git rev-parse --short "$HEAD")
OUT="$HOME/.rh-fix/delta-$SHORT"
mkdir -p "$OUT"

python3 /work/import-closure.py --src src --changed "$BASE" --head "$HEAD" \
  --json --out "$OUT/modules.txt" --explain > "$OUT/closure.json" 2> "$OUT/closure.err"
RC=$?

MODE="closure"
if [ "$RC" -eq 3 ]; then
  MODE="full (config change)"
  TARGETS=(Main Challenge)
else
  SIZE=$(python3 -c "import json;print(json.load(open('$OUT/closure.json'))['closure_size'])" 2>/dev/null || echo 0)
  if [ "${SIZE:-0}" -gt "$LIMIT" ]; then
    MODE="full (closure $SIZE > $LIMIT)"
    TARGETS=(Main Challenge)
  else
    mapfile -t TARGETS < "$OUT/modules.txt"
    if [ "${#TARGETS[@]}" -eq 0 ]; then
      echo "nothing to build" | tee "$OUT/summary.txt"
      exit 0
    fi
  fi
fi

{
  echo "sha=$SHA"
  echo "base=$(git rev-parse "$BASE")"
  echo "mode=$MODE"
  echo "targets=${#TARGETS[@]}"
  python3 -c "import json;d=json.load(open('$OUT/closure.json'));print('changed=%d closure=%d total=%d coverage=%.4f'%(len(d['changed']),d['closure_size'],d['total_modules'],d['coverage']))" 2>/dev/null || true
} > "$OUT/inputs.txt"

echo "delta: $MODE, ${#TARGETS[@]} targets, head $SHORT"
if [ "${DELTA_DRY:-0}" = "1" ]; then
  echo "dry run: not building"
  exit 0
fi
lake build "${TARGETS[@]}" > "$OUT/build.log" 2>&1
BUILD_RC=$?

LAST=$(grep -oE '\[[0-9]+/[0-9]+\]' "$OUT/build.log" | tail -1 | tr -d '[]')
DONE=${LAST%%/*}; TOTAL=${LAST##*/}
FIRST_ERR=$(grep -m1 '^error' "$OUT/build.log" || true)
if command -v sha256sum >/dev/null 2>&1; then LOG_SHA=$(sha256sum "$OUT/build.log" | awk '{print $1}'); else LOG_SHA=$(shasum -a 256 "$OUT/build.log" | awk '{print $1}'); fi

{
  echo "exit=$BUILD_RC"
  echo "jobs_built=${DONE:-0}/${TOTAL:-0}"
  echo "log_sha256=$LOG_SHA"
  echo "first_error=${FIRST_ERR:-none}"
} >> "$OUT/inputs.txt"

{
  echo "# Delta build receipt"
  echo
  cat "$OUT/inputs.txt"
} > "$OUT/RECEIPT.md"

echo "exit=$BUILD_RC jobs=${DONE:-?}/${TOTAL:-?} log=$OUT/build.log"
[ "$BUILD_RC" -eq 0 ] || echo "first error: $FIRST_ERR"
exit "$BUILD_RC"
