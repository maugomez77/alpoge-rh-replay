#!/bin/bash
# Supervisor for the local watchers.
# Usage: supervise.sh start|stop|status|daemon
# Reads watcher commands from ~/.rh-fix/watchers.conf (name|command per line).
set -u
DIR="$HOME/.rh-fix"
PIDS="$DIR/pids"
CONF="$DIR/watchers.conf"
mkdir -p "$PIDS"

[ -f "$CONF" ] || { echo "missing $CONF"; exit 2; }

start_one() {
  local name=$1 cmd=$2 pidf="$PIDS/$1.pid"
  if [ -f "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
    echo "$name: already running ($(cat "$pidf"))"
    return
  fi
  bash -c "$cmd" > "$DIR/$name.log" 2>&1 &
  echo $! > "$pidf"
  echo "$name: started ($!)"
}

cmd_start() {
  while IFS='|' read -r name cmd; do
    case "${name:-}" in ''|\#*) continue ;; esac
    start_one "$name" "$cmd"
  done < "$CONF"
}

cmd_stop() {
  while IFS='|' read -r name cmd; do
    case "${name:-}" in ''|\#*) continue ;; esac
    local pidf="$PIDS/$name.pid"
    [ -f "$pidf" ] || continue
    kill "$(cat "$pidf")" 2>/dev/null && echo "$name: stopped"
    rm -f "$pidf"
  done < "$CONF"
}

cmd_status() {
  while IFS='|' read -r name cmd; do
    case "${name:-}" in ''|\#*) continue ;; esac
    local pidf="$PIDS/$name.pid"
    if [ -f "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
      echo "$name: up ($(cat "$pidf"))"
    else
      echo "$name: down"
    fi
  done < "$CONF"
}

case "${1:-status}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  daemon)
    while true; do cmd_start >/dev/null; sleep 60; done ;;
  *) echo "usage: $0 start|stop|status|daemon"; exit 2 ;;
esac
