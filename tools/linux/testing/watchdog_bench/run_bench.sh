#!/usr/bin/env bash
# Build the watchdog bench against the header in the game tree, guard every
# dumped stock shader and validate each result with spirv-val.
# usage: run_bench.sh [spv_dir]   (default: ~/.local/share/spv)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
header_dir=$(cd "$here/../../../.." && pwd)/glue/rexglue-sdk-main/src/graphics/gta4_native
spv_dir=${1:-$HOME/.local/share/spv}
out=$here/out
rm -rf "$out"
clang++ -std=c++20 -O1 -include cstring -I"$header_dir" "$here/watchdog_bench.cpp" -o "$here/watchdog_bench"
"$here/watchdog_bench" "$out" 16384 "$spv_dir"/*.spv
invalid=0 total=0
for f in "$out"/*.spv; do
  total=$((total + 1))
  if ! msg=$(spirv-val --target-env vulkan1.0 "$f" 2>&1); then
    invalid=$((invalid + 1))
    (( invalid <= 3 )) && echo "INVALID $(basename "$f"): $(echo "$msg" | head -2 | tr '\n' ' ')"
  fi
done
echo "guarded modules: $total, invalid after guarding: $invalid"
