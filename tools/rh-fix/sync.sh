#!/bin/bash
# Sync local watcher state <-> tools/rh-fix/data in the fork.
# Usage: sync.sh pull|push [commit message]
set -u
REPO=${RH_TOOLS_REPO:-/Volumes/Storage/Riemmann/alpoge-rh-replay}
DIR="$HOME/.rh-fix"
cmd=${1:-pull}
git -C "$REPO" checkout -q tools/rh-fix || exit 1

case "$cmd" in
  pull)
    git -C "$REPO" pull -q --rebase fork tools/rh-fix 2>/dev/null || true
    cp "$REPO"/tools/rh-fix/data/*.json "$DIR"/ 2>/dev/null || true
    cp "$REPO"/tools/rh-fix/data/times.txt "$DIR"/ 2>/dev/null || true
    cp "$REPO"/tools/rh-fix/JOURNAL.md "$DIR"/JOURNAL.md 2>/dev/null || true
    echo "pulled state from $REPO"
    ;;
  push)
    mkdir -p "$REPO/tools/rh-fix/data"
    for f in claims.json ledger.json times.txt; do
      [ -f "$DIR/$f" ] && cp "$DIR/$f" "$REPO/tools/rh-fix/data/$f"
    done
    [ -f "$DIR/JOURNAL.md" ] && cp "$DIR/JOURNAL.md" "$REPO/tools/rh-fix/JOURNAL.md"
    git -C "$REPO" add tools/rh-fix
    git -C "$REPO" -c user.name="maugomez77" -c user.email="maugomez77@users.noreply.github.com" \
      commit -q -m "${2:-sync watcher state}" 2>/dev/null || true
    git -C "$REPO" push -q fork tools/rh-fix && echo "pushed state"
    ;;
  *) echo "usage: $0 pull|push [message]"; exit 2 ;;
esac
