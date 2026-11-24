#!/usr/bin/env python3
"""Summarize MangoHud CSV logs: average FPS, 1% / 0.1% lows, worst frame.

usage: fps_summary.py <run_dir> [--skip SECONDS]
--skip drops the first SECONDS of frames (boot, loading screens).
"""
import argparse
import csv
import pathlib
import statistics
import sys


def frame_times_ms(path):
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    # MangoHud writes system-info lines first; the data header starts with "fps".
    for i, row in enumerate(rows):
        if row and row[0] == "fps":
            header, data = row, rows[i + 1:]
            break
    else:
        return []
    col = header.index("frametime")
    return [float(r[col]) for r in data if len(r) > col and r[col]]


def lows(times, fraction):
    worst = sorted(times, reverse=True)[: max(1, int(len(times) * fraction))]
    return 1000.0 / statistics.fmean(worst)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=pathlib.Path)
    parser.add_argument("--skip", type=float, default=0.0)
    args = parser.parse_args()

    logs = sorted((args.run_dir / "mangohud").glob("*.csv"))
    logs = [p for p in logs if not p.name.endswith("_summary.csv")]
    if not logs:
        sys.exit(f"no MangoHud logs in {args.run_dir / 'mangohud'}")

    times = []
    for log in logs:
        times += frame_times_ms(log)
    elapsed, start = 0.0, 0
    for start, t in enumerate(times):
        if elapsed >= args.skip * 1000.0:
            break
        elapsed += t
    times = times[start:]
    if not times:
        sys.exit("no frames after --skip")

    total_s = sum(times) / 1000.0
    print(f"frames      {len(times)} over {total_s:.1f} s")
    print(f"avg fps     {len(times) / total_s:.1f}")
    print(f"1% low      {lows(times, 0.01):.1f}")
    print(f"0.1% low    {lows(times, 0.001):.1f}")
    print(f"worst frame {max(times):.1f} ms")


if __name__ == "__main__":
    main()
