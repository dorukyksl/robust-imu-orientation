"""Bar chart comparing the methods on clean vs disturbed trials.

Run scripts/run_baselines.py first; it writes the CSV file read here.
"""
import argparse
import csv

import numpy as np

ORDER = ["madgwick", "mahony", "vqf", "eskf", "eskf_gated"]
LABELS = {
    "madgwick": "Madgwick",
    "mahony": "Mahony",
    "vqf": "VQF",
    "eskf": "ESKF\n(ours)",
    "eskf_gated": "ESKF + gating\n(ours)",
}

# Colour-blind safe pair, same as in the gyroscope drift figure
BLUE = "#2a78d6"
ORANGE = "#eb6834"


def load_means(path):
    """Mean total RMSE in degrees per method, separately for clean and disturbed trials."""
    with open(path) as f:
        rows = list(csv.DictReader(f))
    methods = [m for m in ORDER if any(r["method"] == m for r in rows)]
    means = {}
    for method in methods:
        errors = [r for r in rows if r["method"] == method]
        means[method] = {
            "clean": np.mean([float(r["total"]) for r in errors if r["disturbed"] == "False"]),
            "disturbed": np.mean([float(r["total"]) for r in errors if r["disturbed"] == "True"]),
        }
    return means


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="results/baselines.csv")
    parser.add_argument("--out", default="results/baselines.png")
    parser.add_argument("--title", default="Standard filters with default parameters (not tuned)")
    args = parser.parse_args()

    means = load_means(args.csv)
    methods = list(means)
    clean = [means[m]["clean"] for m in methods]
    disturbed = [means[m]["disturbed"] for m in methods]

    print("Method      clean  disturbed")
    for m, c, d in zip(methods, clean, disturbed):
        print(f"{m:10s} {c:6.1f}° {d:9.1f}°")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(1.6 * len(methods) + 3, 5))

    # two bars per method, side by side
    x = np.arange(len(methods))
    width = 0.38
    clean_bars = ax.bar(x - width / 2, clean, width, color=BLUE, label="Clean trials")
    disturbed_bars = ax.bar(x + width / 2, disturbed, width, color=ORANGE, label="Disturbed trials")

    ax.set_xticks(x, [LABELS[m] for m in methods])
    ax.set_ylabel("Mean total RMSE (°)")
    ax.set_title(args.title)
    ax.legend()
    ax.bar_label(clean_bars, fmt="%.1f°")
    ax.bar_label(disturbed_bars, fmt="%.1f°")

    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
