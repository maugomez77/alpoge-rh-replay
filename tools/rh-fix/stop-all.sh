#!/bin/bash
# Stop everything local + the M4 build.
# Usage: stop-all.sh [--container]
set -u
DIR=$(cd "$(dirname "$0")" && pwd)
"$DIR/stop-watchers.sh"
"$DIR/stop-m4-build.sh" "${1:-}"
