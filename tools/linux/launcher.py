#!/usr/bin/env python3
"""Liberty Recompiled launcher for the Linux build: pick settings, press Play.

Settings are saved to ~/.config/liberty-recomp/launcher.json and passed to the
game as command-line cvars, so nothing in the game's own config is rewritten.
"""
import json
import os
import pathlib
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

REPO = pathlib.Path(__file__).resolve().parents[2]
GAME = pathlib.Path(os.environ.get("LIBERTY_GAME_BIN", REPO / "out/build/linux-release/LibertyRecomp/bin/LibertyRecomp"))
CONFIG = pathlib.Path.home() / ".config/liberty-recomp/launcher.json"
LOG_DIR = pathlib.Path.home() / ".local/share/LibertyRecomp/logs"

# name: (label, cvar or None for launcher-only, choices)
SETTINGS = {
    "vsync": ("VSync", "gta4_present_mode", {"On": "vsync", "Off": "immediate"}),
    "frame_limit": ("Frame limit", "gta4_frame_limit",
                    {"30": "30", "40": "40", "60": "60", "120": "120", "Unlocked": "0"}),
    "aa": ("Anti-aliasing", "gta4_native_anti_aliasing",
           {"Off": "off", "FXAA": "fxaa", "SMAA": "smaa", "MSAA 2x": "msaa2x", "MSAA 4x": "msaa4x"}),
    "smaa_quality": ("SMAA quality", "gta4_native_smaa_quality",
                     {"Low": "low", "Medium": "medium", "High": "high", "Ultra": "ultra"}),
    "reflections": ("Reflections", "gta4_reflection_resolution",
                    {"Original": "original", "1080p": "1080p", "Full": "full"}),
    "shadows": ("Shadow map", "gta4_shadow_map_base_size",
                {"256": "256", "512": "512", "1024": "1024"}),
    "draw_distance": ("Draw distance", "gta4_draw_distance_scale",
                      {"1x": "1.0", "1.5x": "1.5", "2x": "2.0", "3x": "3.0", "4x": "4.0"}),
    "traffic": ("Traffic density", "gta4_traffic_density_scale",
                {"0.5x": "0.5", "0.75x": "0.75", "1x": "1.0", "1.25x": "1.25"}),
    "peds": ("Pedestrian density", "gta4_ped_density_scale",
             {"0.5x": "0.5", "0.75x": "0.75", "1x": "1.0", "1.25x": "1.25"}),
}
TOGGLES = {
    "fps_overlay": "Show FPS overlay (MangoHud)",
    "hiz_workaround": "Intel GPU hang workaround (keep on)",
    "logging": "Write a log file (for bug reports)",
}
PRESETS = {
    "Performance (iGPU)": {"vsync": "On", "frame_limit": "60", "aa": "FXAA", "smaa_quality": "Low",
                           "reflections": "Original", "shadows": "256", "draw_distance": "1x",
                           "traffic": "0.75x", "peds": "0.75x"},
    "Balanced": {"vsync": "On", "frame_limit": "60", "aa": "SMAA", "smaa_quality": "Medium",
                 "reflections": "Original", "shadows": "512", "draw_distance": "1.5x",
                 "traffic": "1x", "peds": "1x"},
    "Quality (desktop defaults)": {"vsync": "On", "frame_limit": "60", "aa": "SMAA",
                                   "smaa_quality": "High", "reflections": "1080p", "shadows": "512",
                                   "draw_distance": "3x", "traffic": "1.25x", "peds": "1.25x"},
}
DEFAULTS = {**PRESETS["Performance (iGPU)"], "preset": "Performance (iGPU)",
            "fps_overlay": True, "hiz_workaround": True, "logging": False}


def load():
    try:
        return {**DEFAULTS, **json.loads(CONFIG.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(state):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(state, indent=2) + "\n")


def command_and_env(state):
    args = [str(GAME)]
    for name, (_, cvar, choices) in SETTINGS.items():
        args.append(f"--{cvar}={choices[state[name]]}")
    env = dict(os.environ)
    # Stable Wayland app-id for compositor rules (niri: open-fullscreen).
    env["SDL_APP_ID"] = "LibertyRecomp"
    if state["hiz_workaround"]:
        # Mesa ANV hangs on a HiZ fast clear around the multisampled depth/stencil
        # resolve. Disabling fast clears keeps HiZ (about 7% faster than nohiz).
        env["INTEL_DEBUG"] = "nofc"
    if state["fps_overlay"]:
        env["MANGOHUD"] = "1"
        env.setdefault("MANGOHUD_CONFIG", "fps,frametime,gpu_stats,cpu_stats,position=top-left")
    if state["logging"]:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        args += ["--diagnostics=true", "--diagnostics_categories=logging",
                 f"--log_file={LOG_DIR / 'latest.log'}"]
    return args, env


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Liberty Recompiled")
        self.resizable(False, False)
        state = load()
        self.vars = {name: tk.StringVar(value=state[name]) for name in SETTINGS}
        self.toggles = {name: tk.BooleanVar(value=state[name]) for name in TOGGLES}
        self.preset = tk.StringVar(value=state.get("preset", "Custom"))

        frame = ttk.Frame(self, padding=14)
        frame.grid()
        ttk.Label(frame, text="GTA IV — Liberty Recompiled", font=("", 13, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 10), sticky="w")
        ttk.Label(frame, text="Preset").grid(row=1, column=0, sticky="w", pady=2)
        preset_box = ttk.Combobox(frame, textvariable=self.preset, state="readonly", width=24,
                                  values=[*PRESETS, "Custom"])
        preset_box.grid(row=1, column=1, sticky="ew", pady=2)
        preset_box.bind("<<ComboboxSelected>>", self.apply_preset)
        ttk.Separator(frame).grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)

        for row, (name, (label, _, choices)) in enumerate(SETTINGS.items(), start=3):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2, padx=(0, 16))
            box = ttk.Combobox(frame, textvariable=self.vars[name], state="readonly", width=24,
                               values=list(choices))
            box.grid(row=row, column=1, sticky="ew", pady=2)
            box.bind("<<ComboboxSelected>>", lambda _event: self.preset.set("Custom"))
        row = 3 + len(SETTINGS)
        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        for offset, (name, label) in enumerate(TOGGLES.items(), start=1):
            ttk.Checkbutton(frame, text=label, variable=self.toggles[name]).grid(
                row=row + offset, column=0, columnspan=2, sticky="w")
        buttons = ttk.Frame(frame)
        buttons.grid(row=row + len(TOGGLES) + 1, column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(buttons, text="Quit", command=self.destroy).grid(row=0, column=0, padx=4)
        play = ttk.Button(buttons, text="Play", command=self.play)
        play.grid(row=0, column=1)
        play.focus_set()
        self.bind("<Return>", lambda _event: self.play())

    def apply_preset(self, _event=None):
        for name, value in PRESETS.get(self.preset.get(), {}).items():
            self.vars[name].set(value)

    def state(self):
        return {"preset": self.preset.get(),
                **{name: var.get() for name, var in self.vars.items()},
                **{name: var.get() for name, var in self.toggles.items()}}

    def play(self):
        if not GAME.exists():
            messagebox.showerror("Liberty Recompiled", f"Game not found:\n{GAME}")
            return
        state = self.state()
        save(state)
        args, env = command_and_env(state)
        subprocess.Popen(args, env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.destroy()


if __name__ == "__main__":
    Launcher().mainloop()
