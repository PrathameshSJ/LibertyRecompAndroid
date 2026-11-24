#!/usr/bin/env python3
"""Virtual Xbox 360 controller that plays a timed button script (for tests).

usage: padbot.py <script>        script lines: "<seconds> <action> [args]"
actions:
  tap  <BUTTON> [hold_s=0.15]     press and release a button
  hold <BUTTON> <seconds>         keep a button down
  stick <LX|LY|RX|RY> <-1..1> <seconds>   deflect a stick, then recenter
  trigger <LT|RT> <0..1> <seconds>        pull a trigger, then release
  repeat <count> <interval_s> tap <BUTTON>
Times are absolute seconds from start. '#' starts a comment.
Buttons: A B X Y LB RB BACK START GUIDE LS RS UP DOWN LEFT RIGHT
"""
import sys
import threading
import time

from evdev import AbsInfo, UInput, ecodes as e

BUTTONS = {
    "A": e.BTN_SOUTH, "B": e.BTN_EAST, "X": e.BTN_NORTH, "Y": e.BTN_WEST,
    "LB": e.BTN_TL, "RB": e.BTN_TR, "BACK": e.BTN_SELECT, "START": e.BTN_START,
    "GUIDE": e.BTN_MODE, "LS": e.BTN_THUMBL, "RS": e.BTN_THUMBR,
}
DPAD = {"UP": (e.ABS_HAT0Y, -1), "DOWN": (e.ABS_HAT0Y, 1),
        "LEFT": (e.ABS_HAT0X, -1), "RIGHT": (e.ABS_HAT0X, 1)}
STICKS = {"LX": e.ABS_X, "LY": e.ABS_Y, "RX": e.ABS_RX, "RY": e.ABS_RY}
TRIGGERS = {"LT": e.ABS_Z, "RT": e.ABS_RZ}

stick = AbsInfo(value=0, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)
trigger = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
hat = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
CAPS = {
    e.EV_KEY: list(BUTTONS.values()),
    e.EV_ABS: [(code, stick) for code in STICKS.values()]
    + [(code, trigger) for code in TRIGGERS.values()]
    + [(e.ABS_HAT0X, hat), (e.ABS_HAT0Y, hat)],
}

lock = threading.Lock()


def emit(pad, kind, code, value):
    with lock:
        pad.write(kind, code, value)
        pad.syn()


def press(pad, name, down):
    if name in DPAD:
        code, direction = DPAD[name]
        emit(pad, e.EV_ABS, code, direction if down else 0)
    else:
        emit(pad, e.EV_KEY, BUTTONS[name], 1 if down else 0)


def run_action(pad, action, args):
    if action == "tap":
        press(pad, args[0], True)
        time.sleep(float(args[1]) if len(args) > 1 else 0.15)
        press(pad, args[0], False)
    elif action == "hold":
        press(pad, args[0], True)
        time.sleep(float(args[1]))
        press(pad, args[0], False)
    elif action == "stick":
        code = STICKS[args[0]]
        emit(pad, e.EV_ABS, code, int(max(-1.0, min(1.0, float(args[1]))) * 32767))
        time.sleep(float(args[2]))
        emit(pad, e.EV_ABS, code, 0)
    elif action == "trigger":
        code = TRIGGERS[args[0]]
        emit(pad, e.EV_ABS, code, int(max(0.0, min(1.0, float(args[1]))) * 255))
        time.sleep(float(args[2]))
        emit(pad, e.EV_ABS, code, 0)
    elif action == "repeat":
        count, interval = int(args[0]), float(args[1])
        for _ in range(count):
            run_action(pad, args[2], args[3:])
            time.sleep(interval)
    else:
        raise ValueError(f"unknown action {action}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    steps = []
    for line in open(sys.argv[1]):
        line = line.split("#", 1)[0].split()
        if line:
            steps.append((float(line[0]), line[1], line[2:]))
    pad = UInput(CAPS, name="Microsoft X-Box 360 pad", vendor=0x045E, product=0x028E,
                 version=0x110, bustype=e.BUS_USB)
    start = time.monotonic()
    try:
        threads = []
        for at, action, args in sorted(steps, key=lambda s: s[0]):
            time.sleep(max(0.0, start + at - time.monotonic()))
            print(f"padbot {time.monotonic() - start:6.1f}s {action} {' '.join(args)}", flush=True)
            # Actions run concurrently so a held stick does not delay later taps.
            thread = threading.Thread(target=run_action, args=(pad, action, args))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
    finally:
        pad.close()


if __name__ == "__main__":
    main()
