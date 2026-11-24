#!/bin/bash
# Stop the Lean build on the M4.
# Usage: stop-m4-build.sh [--container]
#   default: kill lake/lean inside rhreplay (container keeps running)
#   --container: also stop the container
set -u
HOST=${RH_M4_HOST:-maugomez77@mauricios-macbook-pro-1}
ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" \
  'export PATH="$HOME/.orbstack/bin:$PATH"; docker exec rhreplay bash -lc "pkill -9 -x lean 2>/dev/null; pkill -9 -x lake 2>/dev/null; sleep 2; echo stopped; pgrep -c lake || true"'
if [ "${1:-}" = "--container" ]; then
  ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" \
    'export PATH="$HOME/.orbstack/bin:$PATH"; docker stop rhreplay'
fi
