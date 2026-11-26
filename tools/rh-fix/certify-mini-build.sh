#!/bin/bash
# Clean certification build + exports on the Mac Mini's external drive.
#
# Builds a fresh worktree at the SHA on /Volumes/Storage (1.4 TB), shares only
# .lake/packages, then produces challenge/solution exports. Comparator and
# independent kernels run later in the M4 container with these exports.
#
# Usage: certify-mini-build.sh <sha> [worktree] [outdir]
set -u
export PATH="$HOME/.elan/bin:$PATH"
export LEAN_ABORT_ON_PANIC=1

REPO=${RH_REPO:-/Volumes/Storage/Riemmann/rh120}
SHA=${1:?usage: certify-mini-build.sh <sha> [worktree] [outdir]}
SHORT=$(git -C "$REPO" rev-parse --short "$SHA") || exit 2
WT=${2:-/Volumes/Storage/certify-$SHORT}
OUT=${3:-$HOME/.rh-fix/certify-$SHORT}
mkdir -p "$OUT"

# shellcheck disable=SC1091
source "$(dirname "$0")/disk-guard.sh" 2>/dev/null || true
if command -v disk_guard >/dev/null 2>&1; then
  disk_guard "${CERT_DISK_MIN_GB:-650}" /Volumes/Storage || exit 3
fi

echo "certify-mini: $SHA -> $WT (receipt $OUT)"

if [ ! -d "$WT" ]; then
  git -C "$REPO" worktree add --detach "$WT" "$SHA" || exit 2
fi
mkdir -p "$WT/.lake"
if [ ! -e "$WT/.lake/packages" ]; then
  ln -s "$REPO/.lake/packages" "$WT/.lake/packages" || exit 2
fi

cd "$WT" || exit 2
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DF_BEFORE=$(df -h . | awk 'NR==2 {print $4}')

BUILD=PASS
lake build Main:elabArts Challenge:elabArts > "$OUT/build.log" 2>&1 || BUILD=FAIL
LAST=$(grep -oE '\[[0-9]+/[0-9]+\]' "$OUT/build.log" | tail -1 | tr -d '[]')
FIRST_ERR=$(grep -m1 '^error' "$OUT/build.log" || true)
DIGEST() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}';
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}
BUILD_LOG_SHA=$(DIGEST "$OUT/build.log")

EXPORT_CH=FAIL
EXPORT_SO=FAIL
if [ "$BUILD" = PASS ]; then
  lake env leanexport Challenge -- $(cat export-targets.txt) \
      > "$OUT/challenge.export" 2> "$OUT/challenge.export.err" && EXPORT_CH=PASS
  lake env leanexport Main -- $(cat export-targets.txt) \
      > "$OUT/solution.export" 2> "$OUT/solution.export.err" && EXPORT_SO=PASS
fi
CH_SHA=$(DIGEST "$OUT/challenge.export" 2>/dev/null || echo none)
SO_SHA=$(DIGEST "$OUT/solution.export" 2>/dev/null || echo none)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

{
  echo "# Certification build receipt (Mini)"
  echo
  echo "- sha: \`$(git -C "$WT" rev-parse HEAD)\`"
  echo "- worktree: \`$WT\`"
  echo "- window: $START -> $END"
  echo "- disk free before: $DF_BEFORE"
  echo
  echo "| stage | result |"
  echo "|---|---|"
  echo "| clean build | **$BUILD** (${LAST:-?} jobs, log sha \`$BUILD_LOG_SHA\`) |"
  echo "| challenge export | $EXPORT_CH (sha \`$CH_SHA\`) |"
  echo "| solution export | $EXPORT_SO (sha \`$SO_SHA\`) |"
  echo
  echo "## First build error"
  echo '```'
  echo "${FIRST_ERR:-none}"
  echo '```'
} > "$OUT/BUILD_RECEIPT.md"

echo "build=$BUILD export_ch=$EXPORT_CH export_so=$EXPORT_SO"
echo "exports: $OUT/challenge.export $OUT/solution.export"
echo "receipt: $OUT/BUILD_RECEIPT.md"
[ "$BUILD" = PASS ] && [ "$EXPORT_CH" = PASS ] && [ "$EXPORT_SO" = PASS ]
