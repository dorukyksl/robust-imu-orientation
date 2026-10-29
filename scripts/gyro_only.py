"""Step 1: estimate orientation from the gyroscope alone and watch it drift.

Two variants are compared on all 39 BROAD trials:
- raw:            integrate the gyroscope measurements as they are
- bias removed:   subtract the mean gyroscope reading from the initial rest
                  phase first (a simple one-off bias calibration)

Both start from the true orientation, so every degree of error comes from
integrating the gyroscope.
"""
import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from broad import load_all  # noqa: E402
from metrics import error_quat_earth, rmse_deg, total_error  # noqa: E402
from quat import from_rotation_vector  # noqa: E402

PLOT_TRIAL = "23_undisturbed_fast_combined_360s"


def integrate_gyro(gyr, dt, q0):
    """Chain small rotations: q_k+1 = q_k * dq_k, with dq_k from gyr_k * dt."""
    steps = from_rotation_vector(gyr * dt).tolist()
    w, x, y, z = q0
    out = []
    for dw, dx, dy, dz in steps:
        out.append((w, x, y, z))
        w, x, y, z = (
            w * dw - x * dx - y * dy - z * dz,
            w * dx + x * dw + y * dz - z * dy,
            w * dy - x * dz + y * dw + z * dx,
            w * dz + x * dy - y * dx + z * dw,
        )
        norm = math.sqrt(w * w + x * x + y * y + z * z)
        w, x, y, z = w / norm, x / norm, y / norm, z / norm
    return np.array(out)


def estimate(trial, remove_bias):
    gyr = trial.gyr
    if remove_bias:
        gyr = gyr - trial.gyr[trial.rest].mean(axis=0)
    # start at the first sample where the ground truth is available
    start = int(np.argmax(~np.isnan(trial.quat_ref).any(axis=1)))
    q0 = trial.quat_ref[start]
    quat = np.empty_like(trial.quat_ref)
    quat[:start] = q0
    quat[start:] = integrate_gyro(gyr[start:], trial.dt, q0)
    return quat


def plot_drift(trial, quat_raw, quat_corrected, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, ink_muted, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    blue, orange = "#2a78d6", "#eb6834"

    t = trial.time
    err_raw = np.rad2deg(total_error(error_quat_earth(quat_raw, trial.quat_ref)))
    err_cor = np.rad2deg(total_error(error_quat_earth(quat_corrected, trial.quat_ref)))

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    rest_end = t[trial.rest.stop]
    ax.axvspan(0, rest_end, color=grid, alpha=0.6, lw=0)
    ax.text(rest_end / 2, 0.5, "IMU\nat rest", transform=ax.get_xaxis_transform(),
            ha="center", va="center", fontsize=9, color=ink_muted)

    ax.plot(t, err_raw, color=orange, lw=2, label="Gyroscope only, raw")
    ax.plot(t, err_cor, color=blue, lw=2, label="Gyroscope only, bias removed at rest")

    # direct labels at the line ends
    for err, color in ((err_raw, orange), (err_cor, blue)):
        last = np.flatnonzero(~np.isnan(err))[-1]
        ax.plot(t[last], err[last], "o", ms=8, color=color, mec=surface, mew=2)
        ax.annotate(f"{err[last]:.0f}°", (t[last], err[last]), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=10, color=ink)

    ax.set_title("Integrating the gyroscope alone drifts away from the truth",
                 loc="left", fontsize=13, color=ink, pad=12)
    ax.set_xlabel("Time (s)", color=ink_muted)
    ax.set_ylabel("Orientation error (°)", color=ink_muted)
    ax.set_ylim(bottom=0)
    ax.set_xlim(0, t[-1] * 1.07)
    ax.grid(axis="y", color=grid, lw=0.8)
    ax.tick_params(colors=ink_muted, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.9), frameon=False, labelcolor=ink)
    fig.text(0.01, 0.01, f"BROAD trial {trial.name}. Ground truth: optical motion capture.",
             fontsize=8, color=ink_muted)

    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/broad_hdf5")
    parser.add_argument("--out", default="results")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for trial in load_all(args.data):
        quat_raw = estimate(trial, remove_bias=False)
        quat_cor = estimate(trial, remove_bias=True)
        raw = rmse_deg(quat_raw, trial.quat_ref, trial.movement)
        cor = rmse_deg(quat_cor, trial.quat_ref, trial.movement)
        bias = np.rad2deg(np.linalg.norm(trial.gyr[trial.rest].mean(axis=0)))
        rows.append({"trial": trial.name, "gyro_bias_deg_s": bias,
                     **{f"raw_{k}": v for k, v in raw.items()},
                     **{f"bias_removed_{k}": v for k, v in cor.items()}})
        print(f"{trial.name:42s} bias {bias:4.2f}°/s   "
              f"raw {raw['total']:6.1f}°   bias removed {cor['total']:5.1f}°")
        if trial.name == PLOT_TRIAL:
            plot_drift(trial, quat_raw, quat_cor, out / "gyro_only_drift.png")

    with open(out / "gyro_only.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    for key in ("raw_total", "bias_removed_total"):
        values = [r[key] for r in rows]
        print(f"mean {key}: {np.mean(values):.1f}° over {len(values)} trials")


if __name__ == "__main__":
    main()
