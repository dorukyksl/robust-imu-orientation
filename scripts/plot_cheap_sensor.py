"""Figures for the cheap-sensor test (run scripts/cheap_sensor.py first).

- results/cheap_sensor.png:        all methods along the ladder from the recorded
                                   IMU to a very cheap one
- results/cheap_sensor_sweeps.png: noise, sampling rate and gyroscope bias,
                                   one at a time
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from degrade import LADDER, SWEEPS  # noqa: E402

ORDER = ["madgwick", "mahony", "vqf", "eskf", "eskf_gated"]
LABELS = {
    "madgwick": "Madgwick",
    "mahony": "Mahony",
    "vqf": "VQF",
    "eskf": "ESKF (ours)",
    "eskf_gated": "ESKF + gating (ours)",
}
LADDER_NOTES = {
    "As recorded": "286 Hz",
    "Good consumer": "95 Hz, 2x noise\n+0.5°/s bias",
    "Cheap": "48 Hz, 5x noise\n+1°/s bias",
    "Very cheap": "26 Hz, 10x noise\n+2°/s bias",
}
SWEEP_AXES = {
    "noise": "Sensor noise (x recorded)",
    "rate": "Sampling rate (Hz)",
    "bias": "Extra gyroscope bias (°/s)",
}

# degrade() keeps every k-th sample of the 285.7 Hz recording, so the rates
# actually reached are 285.7 / k: 95, 48 and 26 Hz for the requested 100, 50 and 25
RECORDED_RATE = 285.71

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
GREY = "#a3a29d"
# our gated filter and the strongest rival stand out; the rest stay in the background
STYLE = {
    "eskf_gated": {"color": BLUE, "linewidth": 2.5, "zorder": 4},
    "vqf": {"color": ORANGE, "linewidth": 2.5, "zorder": 3},
    "eskf": {"color": BLUE, "linewidth": 1.5, "linestyle": "--", "zorder": 2},
    "madgwick": {"color": GREY, "linewidth": 1.5, "zorder": 1},
    "mahony": {"color": GREY, "linewidth": 1.5, "linestyle": ":", "zorder": 1},
}


def load_means(path):
    """Mean total RMSE per (degradation, method)."""
    with open(path) as f:
        rows = list(csv.DictReader(f))
    groups = {}
    for r in rows:
        groups.setdefault((r["degradation"], r["method"]), []).append(float(r["total"]))
    return {key: np.mean(values) for key, values in groups.items()}


def key(cond):
    return json.dumps(cond, sort_keys=True)


def style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="results/cheap_sensor.csv")
    parser.add_argument("--out", default="results")
    args = parser.parse_args()

    means = load_means(args.csv)
    methods = [m for m in ORDER if any(k[1] == m for k in means)]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "text.color": INK, "axes.labelcolor": INK})

    # the ladder
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = np.arange(len(LADDER))
    ends = {}
    for m in methods:
        y = [means[(key(c), m)] for c in LADDER.values()]
        ax.plot(x, y, marker="o", markersize=5, label=LABELS[m], **STYLE[m])
        ends[m] = y[-1]
    top = max(ends.values()) * 1.08
    ax.set_ylim(0, top)
    # end labels, pushed apart where lines finish close together
    gap = 0.05 * top
    label_y = -np.inf
    for m in sorted(ends, key=ends.get):
        label_y = max(ends[m], label_y + gap)
        ax.annotate(f"{LABELS[m]}  {ends[m]:.1f}°", (x[-1], ends[m]), xytext=(x[-1] + 0.08, label_y),
                    textcoords="data", va="center", fontsize=9, color=INK)
    ax.set_xticks(x, [f"{name}\n{LADDER_NOTES[name]}" for name in LADDER], fontsize=9)
    ax.set_xlim(-0.2, len(LADDER) - 0.2)
    ax.set_ylabel("Mean orientation error, RMSE (°)")
    ax.set_title("Orientation error as the sensor gets cheaper (39 trials, parameters fixed)",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    style_axes(ax)
    fig.tight_layout()
    path = Path(args.out) / "cheap_sensor.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    print(f"Saved {path}")

    # one factor at a time
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, (factor, values) in zip(axes, SWEEPS.items()):
        base = LADDER["As recorded"]
        xs = values
        if factor == "rate":
            xs = [RECORDED_RATE if v is None else RECORDED_RATE / round(RECORDED_RATE / v) for v in values]
        for m in methods:
            y = [means[(key({**base, factor: v}), m)] for v in values]
            ax.plot(xs, y, marker="o", markersize=4, label=LABELS[m], **STYLE[m])
        ax.set_xlabel(SWEEP_AXES[factor])
        if factor == "rate":
            ax.invert_xaxis()  # cheaper to the right in every panel
        ax.set_ylim(bottom=0)
        style_axes(ax)
    axes[0].set_ylabel("Mean RMSE (°)")
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    path = Path(args.out) / "cheap_sensor_sweeps.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
