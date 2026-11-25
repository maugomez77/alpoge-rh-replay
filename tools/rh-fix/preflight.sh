#!/bin/bash
# Preflight for a build-fix PR. Usage:
#   preflight.sh <Module> [--importers] [--axioms "Ns.thm1 Ns.thm2"]
# Env: RH_REPO (default /Volumes/Storage/Riemmann/rh120), RH_BASE (default origin/opt/collapse-and-consolidate-4.36)
#
# Produces a receipt under ~/.rh-fix/receipts/<timestamp>-<module>/ with:
#   changed-files.txt  opened-scan.txt  statement-diff.txt  build.log
#   importers.txt  axioms.txt (if requested)  digest.txt  RECEIPT.md
set -uo pipefail
REPO="${RH_REPO:-/Volumes/Storage/Riemmann/rh120}"
BASE="${RH_BASE:-origin/opt/collapse-and-consolidate-4.36}"
TOOLS="$HOME/.rh-fix"

MOD="${1:?usage: preflight.sh <Module> [--importers] [--axioms decls]}"; shift || true
BUILD_IMPORTERS=0; AXIOMS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --importers) BUILD_IMPORTERS=1 ;;
    --axioms) AXIOMS="$2"; shift ;;
    *) echo "unknown arg $1"; exit 2 ;;
  esac; shift
done

cd "$REPO" || exit 2
# refresh the base ref so the diff matches the PR's actual base (stale refs inflate changed_inputs)
case "$BASE" in
  origin/*) git fetch -q origin "${BASE#origin/}" 2>/dev/null || true ;;
esac
SHA=$(git rev-parse HEAD)
SHORT=$(echo "$MOD" | tr '.' '_')
OUT="$TOOLS/receipts/$(date +%Y%m%d-%H%M%S)-$SHORT"
mkdir -p "$OUT"
MB=$(git merge-base HEAD "$BASE" 2>/dev/null || echo "$BASE")
RC=0

# 1. changed files + count
git diff --name-only "$MB"..HEAD > "$OUT/changed-files.txt" 2>/dev/null || true
CHANGED=$(cat "$OUT/changed-files.txt")
COUNT=$(printf '%s\n' "$CHANGED" | grep -c . || true)
printf 'base=%s\nhead=%s\nchanged_inputs=%s\n' "$MB" "$SHA" "$COUNT" | tee "$OUT/inputs.txt"

# 2. open-list scan on changed Lean files
printf '%s\n' "$CHANGED" | grep '\.lean$' > "$OUT/lean-files.txt" || true
python3 "$TOOLS/scan-opens.py" $(cat "$OUT/lean-files.txt") > "$OUT/open-scan.txt" 2>&1
if [ -s "$OUT/open-scan.txt" ]; then
  echo "FAIL open-list scan:"; cat "$OUT/open-scan.txt"; RC=1
else
  echo "ok open-list scan"
fi

# 3. statement diff (crude: any changed theorem/lemma/def line)
git diff -U0 "$MB"..HEAD -- $(cat "$OUT/lean-files.txt") 2>/dev/null \
  | grep -E '^[-+](theorem|lemma|noncomputable def|def|abbrev) ' > "$OUT/statement-diff.txt" || true
if [ -s "$OUT/statement-diff.txt" ]; then
  echo "WARN statement lines changed (review):"; head -5 "$OUT/statement-diff.txt"
else
  echo "ok no statement lines changed"
fi

# 4. direct importers
grep -rl --include='*.lean' -E "^(public )?import ${MOD}$" src \
  | sed 's|^src/||; s|\.lean$||; s|/|.|g' > "$OUT/importers.txt" 2>/dev/null || true
echo "importers: $(wc -l < "$OUT/importers.txt" | tr -d ' ')"

# 5. build target (+ importers if asked)
TARGETS="$MOD"
if [ "$BUILD_IMPORTERS" = 1 ]; then TARGETS="$TARGETS $(cat "$OUT/importers.txt")"; fi
echo "building: $TARGETS"
if lake build $TARGETS > "$OUT/build.log" 2>&1; then
  BUILD_STATUS=PASS
  echo "ok build"
else
  BUILD_STATUS=FAIL
  echo "FAIL build (see $OUT/build.log)"; RC=1
fi
grep -E "Built .*$MOD|error: src" "$OUT/build.log" | tail -3

# job coverage: the last [done/total] in the log
LAST_JOB=$(grep -oE '\[[0-9]+/[0-9]+\]' "$OUT/build.log" | tail -1 | tr -d '[]')
JOBS_DONE=${LAST_JOB%%/*}; JOBS_TOTAL=${LAST_JOB##*/}
[ -n "${JOBS_DONE:-}" ] || JOBS_DONE=0
[ -n "${JOBS_TOTAL:-}" ] || JOBS_TOTAL=0
if [ "$JOBS_TOTAL" -gt 0 ] 2>/dev/null; then
  COVERAGE=$(awk -v d="$JOBS_DONE" -v t="$JOBS_TOTAL" 'BEGIN{printf "%.1f", 100*d/t}')
else
  COVERAGE="unknown"
fi
printf 'jobs=%s/%s\ncoverage=%s%%\n' "$JOBS_DONE" "$JOBS_TOTAL" "$COVERAGE" | tee -a "$OUT/inputs.txt"

# 6. axioms (opt-in, names supplied by the caller)
if [ -n "$AXIOMS" ]; then
  { echo "import $MOD"; for d in $AXIOMS; do echo "#print axioms $d"; done; } > "$OUT/Axioms.lean"
  lake env lean "$OUT/Axioms.lean" > "$OUT/axioms.txt" 2>&1 || true
  echo "axioms:"; cat "$OUT/axioms.txt" | tail -5
fi

# 7. log digest
digest() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }
if [ -f "$OUT/build.log" ]; then
  LOG_SHA=$(digest "$OUT/build.log")
  printf 'log_sha256=%s\n' "$LOG_SHA" | tee -a "$OUT/inputs.txt"
fi

# 8. receipt
{
  echo "# Preflight receipt"; echo
  echo "- module: \`$MOD\`"
  echo "- head: \`$SHA\`"
  echo "- base: \`$MB\`"
  echo "- changed inputs: **$COUNT**"
  echo "- importers: $(wc -l < "$OUT/importers.txt" | tr -d ' ')"
  echo "- build jobs: **$JOBS_DONE / $JOBS_TOTAL** (coverage ${COVERAGE}%)"
  [ -n "${LOG_SHA:-}" ] && echo "- build log sha256: \`$LOG_SHA\`"
  echo "- result: $([ "$RC" = 0 ] && echo PASS || echo FAIL)"
  echo
  echo "## Checks"
  echo "- open-list scan: $([ -s "$OUT/open-scan.txt" ] && echo FAIL || echo ok)"
  echo "- statement diff: $([ -s "$OUT/statement-diff.txt" ] && echo REVIEW || echo none)"
  echo
  echo "## Verification ladder"
  echo "| stage | status |"
  echo "|---|---|"
  echo "| build | $BUILD_STATUS (jobs $JOBS_DONE/$JOBS_TOTAL, ${COVERAGE}%) |"
  echo "| clean-machine build | pending |"
  echo "| \`lake comparator\` | pending |"
  echo "| \`con-leche --compare\` | pending |"
  [ -s "$OUT/axioms.txt" ] && { echo; echo "## Axioms"; echo '```'; cat "$OUT/axioms.txt"; echo '```'; }
} > "$OUT/RECEIPT.md"
echo "receipt: $OUT/RECEIPT.md"
echo "next: gh pr ready <N>   (never leave a verified fix as a draft)"
exit $RC
