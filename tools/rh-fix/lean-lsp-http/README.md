# lean-lsp over Streamable HTTP

Supervised replacement for the stdio-over-SSH bridge in
[`../lean-lsp-mcp-remote.sh`](../lean-lsp-mcp-remote.sh).

## Why

With stdio, the MCP "server" is an SSH process. A network drop kills `ssh`
(exit 255), which kills `lean-lsp-mcp` and the Lean LSP, and OpenCode does not
respawn a stdio MCP server after a runtime exit. The server stays failed until
OpenCode is restarted or the server is manually reconnected.

With Streamable HTTP, the MCP server and Lean LSP live in the container and
survive tunnel drops. A local launchd job keeps the tunnel up; a remote launchd
job keeps the HTTP server up. A dropped tunnel produces a transient SSE
disconnect, not a dead server, and the Lean LSP stays warm.

```
OpenCode (local Mac)
  -> http://127.0.0.1:8765/mcp
  -> launchd SSH tunnel
  -> container: lean-lsp-mcp --transport streamable-http :8765
  -> Lean LSP on /work/rh120
```

## Prerequisites

- macOS on both machines, with `launchctl`.
- OpenCode on the local Mac.
- Passwordless SSH to the remote host (`BatchMode=yes`) using a key.
- OrbStack/Docker on the remote host, with the target container **already
  running**. The installer never starts or restarts it.
- Inside the container: `uvx`, `pgrep`, `nice`, and the Lean project.
- Locally: `jq`, `curl`, `plutil`, `launchctl` (`brew install jq` if needed).

## Install

```bash
RH_HOST=you@m4-host tools/rh-fix/lean-lsp-http/install.sh
```

Required:

| Variable | Meaning |
|---|---|
| `RH_HOST` | SSH target of the machine running the container, e.g. `you@m4-host` |

Optional:

| Variable | Default | Meaning |
|---|---|---|
| `RH_CONTAINER` | `rhreplay` | Container name |
| `RH_PROJECT_PATH` | `/work/rh120` | Lean project path inside the container |
| `RH_PORT` | `8765` | Local tunnel and HTTP port |
| `RH_LEAN_LSP_SPEC` | `lean-lsp-mcp==0.33.0` | Pinned `uvx` package spec |
| `RH_LABEL_PREFIX` | `com.maugomez` | launchd label prefix |
| `RH_LOCAL_DIR` | `$HOME/.rh-fix` | Local scripts/logs |
| `RH_LAUNCH_AGENTS` | `$HOME/Library/LaunchAgents` | Local launchd jobs |
| `RH_REMOTE_DIR` | remote `$HOME/.rh-fix` | Remote scripts/logs |
| `RH_STARTUP_TIMEOUT_MS` | `120000` | OpenCode startup timeout |
| `RH_DRY_RUN` | `0` | Check and generate, change nothing |
| `RH_KEEP_TMP` | `0` | Keep generated files for inspection |

Dry run first:

```bash
RH_HOST=you@m4-host RH_DRY_RUN=1 RH_KEEP_TMP=1 \
  tools/rh-fix/lean-lsp-http/install.sh
```

The installer:

1. Verifies SSH and that the container is running.
2. Installs a remote watchdog that starts the HTTP server only when the
   container is running.
3. Installs a local `KeepAlive` SSH tunnel that re-resolves the container IP on
   every restart.
4. Waits for a successful MCP `initialize` over `127.0.0.1:$RH_PORT/mcp`.
5. Writes `.opencode/opencode.json` (`type: remote`, `oauth: false`) and adds it
   to `.git/info/exclude` so the machine-specific endpoint is not committed.

## Verify

```bash
opencode mcp list          # lean-lsp connected
```

In the TUI, `/mcps` shows the connection. The first connect can take ~50s under
a full Lean build; the generated config uses a 120s startup timeout for that
reason.

## Operations

Status:

```bash
launchctl print gui/$(id -u)/com.maugomez.lean-lsp-tunnel
ssh you@m4-host "launchctl print gui/\$(id -u)/com.maugomez.lean-lsp-http"
```

Restart the tunnel:

```bash
launchctl kickstart -k gui/$(id -u)/com.maugomez.lean-lsp-tunnel
```

Restart the HTTP server (the watchdog also restarts it within 30s):

```bash
ssh you@m4-host \
  "export PATH=\$HOME/.orbstack/bin:\$PATH; \
   docker exec rhreplay pkill -f '[l]ean-lsp-mcp --transport streamable-http'"
```

Logs:

- Local tunnel: `~/.rh-fix/lean-lsp-http-tunnel.log`
- Remote watchdog: remote `~/.rh-fix/lean-lsp-http-supervise.log`
- Container server: `docker exec rhreplay cat /tmp/lean-lsp-http.log`

## Caveats

- If the container is **recreated** (not merely restarted) it may get a new IP.
  Restart the local tunnel so it re-resolves the IP.
- The watchdog deliberately does not start a stopped container. After an
  intentional stop, start the container as usual; the server returns within
  30s.
- A tunnel drop recovers by itself. If the HTTP server process dies, the remote
  watchdog restarts it within 30s; OpenCode may then need `/mcps` reconnect.
- The HTTP server binds inside the container only. No port is published to the
  LAN; the tunnel listens on `127.0.0.1`.

## Rollback

Restore the project config backup created by the installer, then unload the
agents:

```bash
launchctl bootout gui/$(id -u)/com.maugomez.lean-lsp-tunnel
ssh you@m4-host "launchctl bootout gui/\$(id -u)/com.maugomez.lean-lsp-http"
```

The legacy stdio wrapper `../lean-lsp-mcp-remote.sh` is untouched.
