#!/bin/bash
# Stop the local watchers (GitHub watcher + work-finder). Does NOT touch the M4 build.
# Usage: stop-watchers.sh
set -u
for pat in watch-github.py work-finder.py; do
  pids=$(pgrep -f "$pat" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null && echo "stopped $pat ($pids)"
  else
    echo "not running: $pat"
  fi
done
