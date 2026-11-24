#!/usr/bin/env bash
# One GPU-hang bisection step: boot the game headless with the given extra
# arguments and report whether the kernel logged a new GPU hang.
# usage: hang_probe.sh <name> [game args...]      (SECONDS_BUDGET, default 85)
set -euo pipefail
name=${1:?usage: hang_probe.sh <name> [game args...]}
shift
here=$(cd "$(dirname "$0")" && pwd)
before=$(sudo dmesg | grep -c 'GPU HANG' || true)
RUN_NAME="probe-$name" SHOT_EVERY=40 MANGOHUD=0 \
  timeout $(( ${SECONDS_BUDGET:-50} + 90 )) "$here/run_headless.sh" "${SECONDS_BUDGET:-50}" "$@" >/dev/null 2>&1 || true
after=$(sudo dmesg | grep -c 'GPU HANG' || true)
log="$here/runs/probe-$name/rex.log"
failures=$(grep -c 'failed to publish' "$log" 2>/dev/null || true)
frames=$(grep -oE 'frame=[0-9]+' "$log" 2>/dev/null | tail -1 || true)
if (( after > before )); then verdict=HANG; else verdict=ok; fi
printf '%-24s %-5s publish-failures=%-6s last %s\n' "$name" "$verdict" "${failures:-0}" "${frames:-frame=?}"
