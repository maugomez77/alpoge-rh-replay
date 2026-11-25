#!/bin/bash
# Shared disk-headroom guard for build scripts.
#
# Usage:
#   source "$(dirname "$0")/disk-guard.sh"
#   disk_guard [min_gb] [path] || exit 3
#
# Checks the filesystem containing the build tree. When run on a macOS host
# (where /System/Volumes/Data exists) it also checks host free space, because
# OrbStack's sparse data.img.raw can fill the host while the VM still reports
# free space -- that is what force-stopped the VM on 2026-11-25.
#
# Env:
#   DISK_MIN_GB       minimum free GB inside the build filesystem (default 100)
#   HOST_DISK_MIN_GB  minimum free GB on the macOS host (default 80)
set -u

_disk_free_gb() {
  df -Pk "$1" 2>/dev/null | awk 'NR==2 {printf "%d", $4/1048576}'
}

disk_guard() {
  local min="${1:-${DISK_MIN_GB:-100}}"
  local path="${2:-${RH_REPO:-/work/rh120}}"
  local free hostfree hmin rc=0

  free=$(_disk_free_gb "$path")
  if [ -z "$free" ]; then
    echo "disk-guard: cannot stat $path (skipped)" >&2
  else
    echo "disk-guard: ${free}G free on $path (min ${min}G)"
    [ "$free" -lt "$min" ] && rc=3
  fi

  if [ -d /System/Volumes/Data ]; then
    hmin="${HOST_DISK_MIN_GB:-80}"
    hostfree=$(_disk_free_gb /System/Volumes/Data)
    if [ -n "$hostfree" ]; then
      echo "disk-guard: ${hostfree}G free on host (min ${hmin}G)"
      [ "$hostfree" -lt "$hmin" ] && rc=3
    fi
  fi

  if [ "$rc" -eq 3 ]; then
    echo "disk-guard: free space below threshold; aborting build" >&2
  fi
  return "$rc"
}
