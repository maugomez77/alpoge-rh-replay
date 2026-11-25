#!/bin/bash
# Stream lean-lsp-mcp (stdio) from the M4 container to the local MCP client.
# OpenCode connects to this script as a local MCP server.
set -u
HOST=${RH_M4_HOST:-maugomez77@mauricios-macbook-pro-1}
exec ssh -o BatchMode=yes -o ServerAliveInterval=30 -o ConnectTimeout=10 "$HOST" \
  "export PATH=\$HOME/.orbstack/bin:\$PATH; docker start rhreplay >/dev/null 2>&1; docker exec -i rhreplay bash -lc 'export PATH=\$HOME/.local/bin:/root/.elan/bin:\$PATH; export LEAN_PROJECT_PATH=/work/rh120; export LEAN_LOG_LEVEL=ERROR; cd /work/rh120; exec uvx lean-lsp-mcp --transport stdio'"
