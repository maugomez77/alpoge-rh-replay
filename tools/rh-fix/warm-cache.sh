#!/bin/bash
# Try to restore the project's validated CI cache for the current inputs.
# Exit 0 always: a missing cache (exit 3) simply means "build required".
# Run inside the project checkout (or set RH_REPO).
set -u
cd "${RH_REPO:-/work/rh120}" || exit 2
out=$(lake exe cache get 2>&1)
rc=$?
echo "$out" | tail -6
case "$rc" in
  0) echo "cache restored for $(git rev-parse --short HEAD)" ;;
  3) echo "no validated cache for $(git rev-parse --short HEAD); build required" ;;
  *) echo "cache fetch error (exit $rc)" ;;
esac
exit 0
