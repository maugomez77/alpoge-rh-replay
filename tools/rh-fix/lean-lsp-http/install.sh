#!/bin/bash
# Install a supervised Streamable HTTP bridge to lean-lsp-mcp on a remote
# OrbStack/Docker host (the "M4").
#
#   RH_HOST=you@m4-host tools/rh-fix/lean-lsp-http/install.sh
#
# Optional:
#   RH_CONTAINER=rhreplay            container name
#   RH_PROJECT_PATH=/work/rh120      Lean project inside the container
#   RH_PORT=8765                     local tunnel / server port
#   RH_LEAN_LSP_SPEC=lean-lsp-mcp==0.33.0
#   RH_LABEL_PREFIX=com.maugomez     launchd label prefix
#   RH_LOCAL_DIR=$HOME/.rh-fix       local script/log directory
#   RH_LAUNCH_AGENTS=$HOME/Library/LaunchAgents
#   RH_DRY_RUN=1                     check and generate, change nothing
#   RH_KEEP_TMP=1                    keep generated files for inspection
#
# The container must already be running. This installer never starts or
# restarts it, and never touches running Lean builds.
set -euo pipefail

RH_HOST=${RH_HOST:-}
RH_CONTAINER=${RH_CONTAINER:-rhreplay}
RH_PROJECT_PATH=${RH_PROJECT_PATH:-/work/rh120}
RH_PORT=${RH_PORT:-8765}
RH_LEAN_LSP_SPEC=${RH_LEAN_LSP_SPEC:-lean-lsp-mcp==0.33.0}
RH_LABEL_PREFIX=${RH_LABEL_PREFIX:-com.maugomez}
RH_LOCAL_DIR=${RH_LOCAL_DIR:-$HOME/.rh-fix}
RH_LAUNCH_AGENTS=${RH_LAUNCH_AGENTS:-$HOME/Library/LaunchAgents}
RH_DRY_RUN=${RH_DRY_RUN:-0}
RH_KEEP_TMP=${RH_KEEP_TMP:-0}
RH_STARTUP_TIMEOUT_MS=${RH_STARTUP_TIMEOUT_MS:-120000}

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ -n "$RH_HOST" ] || die "RH_HOST is required (example: RH_HOST=you@m4-host $0)"
case "$RH_HOST" in *[!A-Za-z0-9_.@:-]*) die "RH_HOST contains unsupported characters" ;; esac
case "$RH_CONTAINER" in *[!A-Za-z0-9_.-]*) die "RH_CONTAINER contains unsupported characters" ;; esac
case "$RH_PORT" in ''|*[!0-9]*) die "RH_PORT must be numeric" ;; esac
[ "$RH_PORT" -ge 1 ] && [ "$RH_PORT" -le 65535 ] || die "RH_PORT out of range"
case "$RH_PROJECT_PATH" in *[\|\&\'\`\$\"]*) die "RH_PROJECT_PATH contains unsupported characters" ;; esac
case "$RH_LEAN_LSP_SPEC" in *[\|\&\'\`\$\"]*) die "RH_LEAN_LSP_SPEC contains unsupported characters" ;; esac
case "$RH_LABEL_PREFIX" in *[!A-Za-z0-9.-]*) die "RH_LABEL_PREFIX contains unsupported characters" ;; esac
case "$RH_STARTUP_TIMEOUT_MS" in ''|*[!0-9]*) die "RH_STARTUP_TIMEOUT_MS must be numeric" ;; esac

for c in ssh scp curl plutil launchctl mktemp jq; do
  command -v "$c" >/dev/null 2>&1 || die "missing required command: $c"
done

say "== checking $RH_HOST =="
ssh -o BatchMode=yes -o ConnectTimeout=10 "$RH_HOST" true \
  || die "cannot SSH to $RH_HOST with BatchMode (check your key and known_hosts)"
REMOTE_HOME=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$RH_HOST" 'printf %s "$HOME"')
REMOTE_UID=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$RH_HOST" 'id -u')
REMOTE_DIR=${RH_REMOTE_DIR:-$REMOTE_HOME/.rh-fix}
REMOTE_LAUNCH_AGENTS="$REMOTE_HOME/Library/LaunchAgents"

RUNNING=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$RH_HOST" \
  "export PATH=\$HOME/.orbstack/bin:\$PATH; docker inspect -f '{{.State.Running}}' '$RH_CONTAINER' 2>/dev/null || true")
[ "$RUNNING" = "true" ] || die "container '$RH_CONTAINER' is not running on $RH_HOST; start it first (this installer never starts it)"

ssh -o BatchMode=yes -o ConnectTimeout=10 "$RH_HOST" \
  "export PATH=\$HOME/.orbstack/bin:\$PATH; docker exec '$RH_CONTAINER' bash -lc 'for c in uvx pgrep nice; do command -v \$c >/dev/null || { echo missing:\$c; exit 1; }; done'" \
  || die "container '$RH_CONTAINER' is missing uvx, pgrep, or nice"

TMP=$(mktemp -d)
cleanup() { [ "$RH_KEEP_TMP" = "1" ] || rm -rf "$TMP"; }
trap cleanup EXIT

say "== generating files =="

# --- remote watchdog -------------------------------------------------------
cat > "$TMP/lean-lsp-http-supervise.sh" <<'EOS'
#!/bin/bash
# Keep lean-lsp-mcp (Streamable HTTP) running inside the container.
# Never starts a stopped container.
set -uo pipefail

export PATH="$HOME/.orbstack/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
CONTAINER="__CONTAINER__"
PORT="__PORT__"
PROJECT="__PROJECT__"
SPEC="__SPEC__"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LOG="$SCRIPT_DIR/lean-lsp-http-supervise.log"
mkdir -p "$SCRIPT_DIR"

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
  exit 0
fi

if docker exec "$CONTAINER" pgrep -f '[l]ean-lsp-mcp --transport streamable-http' >/dev/null 2>&1; then
  exit 0
fi

echo "$(date -u +%FT%TZ) starting lean-lsp-mcp HTTP on :$PORT" >> "$LOG"
if ! docker exec -d "$CONTAINER" bash -lc "export PATH=\$HOME/.local/bin:/root/.elan/bin:\$PATH; export LEAN_PROJECT_PATH='$PROJECT'; export LEAN_LOG_LEVEL=ERROR; cd '$PROJECT'; exec nice -n 10 uvx --from '$SPEC' lean-lsp-mcp --transport streamable-http --host 0.0.0.0 --port $PORT </dev/null >>/tmp/lean-lsp-http.log 2>&1"; then
  echo "$(date -u +%FT%TZ) failed to start lean-lsp-mcp HTTP" >> "$LOG"
fi
EOS
sed -i '' \
  -e "s|__CONTAINER__|$RH_CONTAINER|g" \
  -e "s|__PORT__|$RH_PORT|g" \
  -e "s|__PROJECT__|$RH_PROJECT_PATH|g" \
  -e "s|__SPEC__|$RH_LEAN_LSP_SPEC|g" \
  "$TMP/lean-lsp-http-supervise.sh"

# --- remote launchd job ----------------------------------------------------
cat > "$TMP/$RH_LABEL_PREFIX.lean-lsp-http.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$RH_LABEL_PREFIX.lean-lsp-http</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REMOTE_DIR/lean-lsp-http-supervise.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>$REMOTE_DIR/lean-lsp-http-supervise.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$REMOTE_DIR/lean-lsp-http-supervise.launchd.log</string>
</dict>
</plist>
EOF

# --- local tunnel ----------------------------------------------------------
cat > "$TMP/lean-lsp-http-tunnel.sh" <<'EOS'
#!/bin/bash
# Keep a local port forward to the lean-lsp-mcp HTTP server in the container.
# launchd restarts this script whenever it exits.
set -uo pipefail

HOST="__HOST__"
CONTAINER="__CONTAINER__"
PORT="__PORT__"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LOG="$SCRIPT_DIR/lean-lsp-http-tunnel.log"
mkdir -p "$SCRIPT_DIR"

IP=$(/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" \
  "export PATH=\$HOME/.orbstack/bin:\$PATH; docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $CONTAINER" 2>/dev/null \
  | tr -d '[:space:]')

if [ -z "$IP" ]; then
  echo "$(date -u +%FT%TZ) could not resolve $CONTAINER IP" >> "$LOG"
  exit 1
fi

echo "$(date -u +%FT%TZ) forwarding 127.0.0.1:$PORT -> $IP:$PORT" >> "$LOG"
exec /usr/bin/ssh -N \
  -o BatchMode=yes \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -o TCPKeepAlive=yes \
  -o ConnectTimeout=10 \
  -L "127.0.0.1:$PORT:$IP:$PORT" \
  "$HOST" >> "$LOG" 2>&1
EOS
sed -i '' \
  -e "s|__HOST__|$RH_HOST|g" \
  -e "s|__CONTAINER__|$RH_CONTAINER|g" \
  -e "s|__PORT__|$RH_PORT|g" \
  "$TMP/lean-lsp-http-tunnel.sh"

# --- local launchd job -----------------------------------------------------
cat > "$TMP/$RH_LABEL_PREFIX.lean-lsp-tunnel.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$RH_LABEL_PREFIX.lean-lsp-tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RH_LOCAL_DIR/lean-lsp-http-tunnel.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>$RH_LOCAL_DIR/lean-lsp-http-tunnel.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$RH_LOCAL_DIR/lean-lsp-http-tunnel.launchd.log</string>
</dict>
</plist>
EOF

plutil -lint "$TMP/$RH_LABEL_PREFIX.lean-lsp-http.plist" >/dev/null
plutil -lint "$TMP/$RH_LABEL_PREFIX.lean-lsp-tunnel.plist" >/dev/null
bash -n "$TMP/lean-lsp-http-supervise.sh"
bash -n "$TMP/lean-lsp-http-tunnel.sh"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$SCRIPT_DIR")
CFG="$ROOT/.opencode/opencode.json"

if [ "$RH_DRY_RUN" = "1" ]; then
  say "== dry run: no changes made =="
  say "remote script: $RH_HOST:$REMOTE_DIR/lean-lsp-http-supervise.sh"
  say "remote agent:  $RH_HOST:$REMOTE_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-http.plist"
  say "local script:  $RH_LOCAL_DIR/lean-lsp-http-tunnel.sh"
  say "local agent:   $RH_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-tunnel.plist"
  say "config:        $CFG"
  [ "$RH_KEEP_TMP" = "1" ] && say "generated:     $TMP"
  exit 0
fi

say "== installing remote watchdog =="
ssh -o BatchMode=yes -o ConnectTimeout=10 "$RH_HOST" \
  "mkdir -p '$REMOTE_DIR' '$REMOTE_LAUNCH_AGENTS'"
scp -q "$TMP/lean-lsp-http-supervise.sh" \
  "$RH_HOST:$REMOTE_DIR/lean-lsp-http-supervise.sh"
scp -q "$TMP/$RH_LABEL_PREFIX.lean-lsp-http.plist" \
  "$RH_HOST:$REMOTE_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-http.plist"
ssh -o BatchMode=yes -o ConnectTimeout=10 "$RH_HOST" \
  "chmod +x '$REMOTE_DIR/lean-lsp-http-supervise.sh'; \
   plutil -lint '$REMOTE_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-http.plist' >/dev/null; \
   launchctl bootout gui/$REMOTE_UID/$RH_LABEL_PREFIX.lean-lsp-http 2>/dev/null || true; \
   launchctl bootstrap gui/$REMOTE_UID '$REMOTE_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-http.plist'" \
  || die "failed to load the remote LaunchAgent; run the bootstrap manually on $RH_HOST"

say "== installing local tunnel =="
mkdir -p "$RH_LOCAL_DIR" "$RH_LAUNCH_AGENTS"
cp "$TMP/lean-lsp-http-tunnel.sh" "$RH_LOCAL_DIR/lean-lsp-http-tunnel.sh"
chmod +x "$RH_LOCAL_DIR/lean-lsp-http-tunnel.sh"
cp "$TMP/$RH_LABEL_PREFIX.lean-lsp-tunnel.plist" \
  "$RH_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-tunnel.plist"
launchctl bootout "gui/$(id -u)/$RH_LABEL_PREFIX.lean-lsp-tunnel" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" \
  "$RH_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-tunnel.plist" \
  || die "failed to load the local LaunchAgent"

say "== waiting for the MCP endpoint =="
CODE=""
for _ in $(seq 1 30); do
  CODE=$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' \
    -X POST "http://127.0.0.1:$RH_PORT/mcp" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"installer","version":"1.0"}}}' \
    2>/dev/null || true)
  [ "$CODE" = "200" ] && break
  sleep 2
done
[ "$CODE" = "200" ] || die "endpoint did not come up; see $RH_LOCAL_DIR/lean-lsp-http-tunnel.log and $RH_HOST:$REMOTE_DIR/lean-lsp-http-supervise.log"

say "== writing OpenCode project config =="
mkdir -p "$(dirname "$CFG")"
ENTRY=$(printf '{"type":"remote","url":"http://127.0.0.1:%s/mcp","oauth":false,"timeout":{"startup":%s,"catalog":60000}}' \
  "$RH_PORT" "$RH_STARTUP_TIMEOUT_MS")
if [ -f "$CFG" ]; then
  jq empty "$CFG" >/dev/null 2>&1 || die "$CFG is not plain JSON; back it up and merge the lean-lsp entry manually"
  cp "$CFG" "$CFG.bak.$(date +%Y%m%d-%H%M%S)"
  jq --argjson entry "$ENTRY" \
    '.mcp = (.mcp // {}) | .mcp.servers = (.mcp.servers // {}) | .mcp.servers["lean-lsp"] = $entry' \
    "$CFG" > "$CFG.tmp" && mv "$CFG.tmp" "$CFG"
else
  jq -n --argjson entry "$ENTRY" \
    '{"$schema":"https://opencode.ai/config.json","mcp":{"servers":{"lean-lsp":$entry}}}' > "$CFG"
fi

if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  EXCLUDE=$(cd "$ROOT" && git rev-parse --git-path info/exclude)
  case "$EXCLUDE" in /*) ;; *) EXCLUDE="$ROOT/$EXCLUDE" ;; esac
  if ! grep -qxF '.opencode/opencode.json' "$EXCLUDE" 2>/dev/null; then
    printf '\n# Local OpenCode MCP config (machine-specific)\n.opencode/opencode.json\n' >> "$EXCLUDE"
  fi
fi

say ""
say "installed:"
say "  local tunnel : $RH_LOCAL_DIR/lean-lsp-http-tunnel.sh"
say "  local agent  : $RH_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-tunnel.plist"
say "  remote agent : $RH_HOST:$REMOTE_LAUNCH_AGENTS/$RH_LABEL_PREFIX.lean-lsp-http.plist"
say "  config       : $CFG"
say ""
say "next: opencode mcp list   (or /mcps in the TUI)"
say "first connect can take ~50s under a full build; startup timeout is ${RH_STARTUP_TIMEOUT_MS}ms"
say "rollback: restore the .bak config and bootout the two agents"
