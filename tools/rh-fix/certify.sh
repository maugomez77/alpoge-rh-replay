#!/bin/bash
# Clean-source certification at a pinned SHA.
#
# IR is intrinsic to Lake's module system: `elabArts` still builds .ir/.c for
# dependencies because importers fetch `metaExportInfo` → `irArts`. A clean
# build therefore needs ~537 GB (464 GB IR + 73 GB oleans). Run certification
# on a volume with >=600 GB free. The exports/comparator stages still apply.
#
# Usage: certify.sh <sha> [worktree] [outdir]
# Requires: bubblewrap, a warm $RH_REPO with .lake/packages (Mathlib artifacts).
set -u
export PATH=/root/.elan/bin:$PATH
export LEAN_ABORT_ON_PANIC=1

REPO=${RH_REPO:-/work/rh120}
SHA=${1:?usage: certify.sh <sha> [worktree] [outdir]}
SHORT=$(git -C "$REPO" rev-parse --short "$SHA") || exit 2
WT=${2:-/work/certify-$SHORT}
OUT=${3:-$HOME/.rh-fix/certify-$SHORT}
mkdir -p "$OUT"

# Disk guard: certification needs ~73 GB of oleans plus the shared packages.
# shellcheck disable=SC1091
source "$(dirname "$0")/disk-guard.sh" 2>/dev/null || true
if command -v disk_guard >/dev/null 2>&1; then
  disk_guard "${CERT_DISK_MIN_GB:-600}" "$REPO" || exit 3
fi

echo "certify: $SHA -> $WT (receipt $OUT)"

# 1. fresh worktree, fresh project artifacts; share only the dependency packages
if [ ! -d "$WT" ]; then
  git -C "$REPO" worktree add --detach "$WT" "$SHA" || exit 2
fi
mkdir -p "$WT/.lake"
if [ ! -e "$WT/.lake/packages" ]; then
  ln -s "$REPO/.lake/packages" "$WT/.lake/packages" || exit 2
fi

cd "$WT" || exit 2
DF_BEFORE=$(df -h . | awk 'NR==2 {print $4}')

# 2. clean source build (IR is intrinsic; ~537 GB)
BUILD=PASS
lake build Main:elabArts Challenge:elabArts > "$OUT/build.log" 2>&1 || BUILD=FAIL
LAST=$(grep -oE '\[[0-9]+/[0-9]+\]' "$OUT/build.log" | tail -1 | tr -d '[]')
FIRST_ERR=$(grep -m1 '^error' "$OUT/build.log" || true)
if command -v sha256sum >/dev/null 2>&1; then DIGEST() { sha256sum "$1" | awk '{print $1}'; }; else DIGEST() { shasum -a 256 "$1" | awk '{print $1}'; }; fi
BUILD_LOG_SHA=$(DIGEST "$OUT/build.log")

# 3. export the named constants from both modules
EXPORT=PASS
lake env leanexport Challenge -- $(cat export-targets.txt) > "$OUT/challenge.export" 2> "$OUT/challenge.export.err" || EXPORT=FAIL
lake env leanexport Main -- $(cat export-targets.txt) > "$OUT/solution.export" 2> "$OUT/solution.export.err" || EXPORT=FAIL
CH_SHA=$(DIGEST "$OUT/challenge.export" 2>/dev/null || echo none)
SO_SHA=$(DIGEST "$OUT/solution.export" 2>/dev/null || echo none)

# 4. judge against the challenge (sandboxed; no rebuild)
COMP=PASS
lake comparator --config comparator.json \
  --challenge-from-export "$OUT/challenge.export" \
  --solution-from-export "$OUT/solution.export" > "$OUT/comparator.log" 2>&1 || COMP=FAIL

# 5. independent kernels on the solution export
CONLECHE=SKIP
if lake env con-leche --verified --jobs=8 "$OUT/solution.export" > "$OUT/conleche.log" 2>&1; then CONLECHE=PASS; else CONLECHE=FAIL; fi
LEANCHECK=SKIP
if lake env leanchecker-paranoid --silent --from-export "$OUT/solution.export" > "$OUT/leanchecker.log" 2>&1; then LEANCHECK=PASS; else LEANCHECK=FAIL; fi

# 6. receipt
{
  echo "# Certification receipt"
  echo
  echo "- sha: \`$(git -C "$WT" rev-parse HEAD)\`"
  echo "- worktree: \`$WT\`"
  echo "- timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- disk free before: $DF_BEFORE"
  echo
  echo "| stage | result |"
  echo "|---|---|"
  echo "| build \`Main:olean Challenge:olean\` | **$BUILD** (${LAST:-?} jobs, log sha \`$BUILD_LOG_SHA\`) |"
  echo "| challenge export | $EXPORT (sha \`$CH_SHA\`) |"
  echo "| solution export | $EXPORT (sha \`$SO_SHA\`) |"
  echo "| \`lake comparator\` | **$COMP** |"
  echo "| \`con-leche --verified\` | $CONLECHE |"
  echo "| \`leanchecker-paranoid\` | $LEANCHECK |"
  echo
  echo "## First build error"
  echo '```'
  echo "${FIRST_ERR:-none}"
  echo '```'
  echo
  echo "## Comparator tail"
  echo '```'
  tail -20 "$OUT/comparator.log" 2>/dev/null
  echo '```'
} > "$OUT/RECEIPT.md"

echo "build=$BUILD comparator=$COMP con-leche=$CONLECHE leanchecker=$LEANCHECK"
echo "receipt: $OUT/RECEIPT.md"
[ "$BUILD" = PASS ] && [ "$COMP" = PASS ] && [ "$CONLECHE" = PASS ] && [ "$LEANCHECK" = PASS ]
