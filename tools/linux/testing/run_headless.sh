#!/usr/bin/env bash
# Run the Linux LibertyRecomp build off-screen for a bounded time and collect
# the game log, MangoHud frame times and periodic screenshots.
#
# usage: run_headless.sh <seconds> [game args...]
# env:   DIAG_CATEGORIES (default: logging), RUN_NAME (default: timestamp), SHOT_EVERY (default: 15 s),
#        WIDTH/HEIGHT of the headless output (default 1920x1080)
set -euo pipefail

duration=${1:?usage: run_headless.sh <seconds> [game args...]}
shift

root=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$root/../../.." && pwd)
game_bin=${GAME_BIN:-$repo/out/build/linux-release/LibertyRecomp/bin/LibertyRecomp}
run_dir="$root/runs/${RUN_NAME:-$(date +%Y%m%d-%H%M%S)}"
shot_every=${SHOT_EVERY:-15}
mkdir -p "$run_dir/shots" "$run_dir/mangohud"

[[ -x $game_bin ]] || { echo "game binary not found: $game_bin" >&2; exit 2; }

# Session script run inside cage: start the game, screenshot it on a timer,
# stop everything when the time is up.
session="$run_dir/session.sh"
cat > "$session" <<EOF
#!/usr/bin/env bash
pad=
if [[ -n "${PAD_SCRIPT:-}" ]]; then
  python3 -I "$root/padbot.py" "${PAD_SCRIPT:-}" > "$run_dir/padbot.log" 2>&1 &
  pad=\$!
fi
"$game_bin" --diagnostics=true --diagnostics_categories="${DIAG_CATEGORIES:-logging}" --log_file="$run_dir/rex.log" --log_flush_interval=1 "\$@" > "$run_dir/game.log" 2>&1 &
game=\$!
end=\$((SECONDS + $duration))
n=0
while kill -0 "\$game" 2>/dev/null && (( SECONDS < end )); do
  sleep $shot_every
  grim "$run_dir/shots/\$(printf %04d \$n).png" 2>/dev/null || true
  n=\$((n + 1))
done
if kill -0 "\$game" 2>/dev/null; then
  echo "harness: time limit reached, stopping game" >> "$run_dir/game.log"
  kill -TERM "\$game"; sleep 5; kill -KILL "\$game" 2>/dev/null || true
fi
wait "\$game"; echo "harness: game exit status \$?" >> "$run_dir/game.log"
[[ -n "\$pad" ]] && kill "\$pad" 2>/dev/null
EOF
chmod +x "$session"

export WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1
export WLR_HEADLESS_OUTPUTS=1
export SDL_AUDIO_DRIVER=dummy
# With a virtual pad, hide real controllers so the bot is player 1.
if [[ -n "${PAD_SCRIPT:-}" ]]; then
  export SDL_GAMECONTROLLER_IGNORE_DEVICES="0x045e/0x0b13,0x045e/0x0b12,0x045e/0x0b20"
fi
export MANGOHUD=${MANGOHUD:-1}
export MANGOHUD_CONFIG=${MANGOHUD_CONFIG:-"no_display,output_folder=$run_dir/mangohud,autostart_log=1,log_interval=0"}

# Outer timeout: the session budget plus margin for startup and shutdown.
# Run it in its own process group so that stopping this script (Ctrl-C, a
# task stop) also tears down cage and the game instead of orphaning them.
setsid timeout --kill-after=10 $((duration + 60)) \
  cage -s -- "$session" "$@" > "$run_dir/cage.log" 2>&1 &
group=$!
trap 'kill -TERM -- -"$group" 2>/dev/null; sleep 5; kill -KILL -- -"$group" 2>/dev/null' INT TERM HUP
wait "$group" || echo "cage exit $?" >> "$run_dir/cage.log"
trap - INT TERM HUP

echo "$run_dir"
