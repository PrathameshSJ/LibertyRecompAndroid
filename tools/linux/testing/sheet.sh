#!/usr/bin/env bash
# Tile a run's screenshots into one labelled contact sheet: sheet.sh <run_dir>
set -euo pipefail
shots=("$1"/shots/*.png)
magick montage "${shots[@]}" -resize 480x270 -tile 4x -geometry +2+2 -label '%t' "$1/sheet.png"
echo "$1/sheet.png"
