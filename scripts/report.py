"""Markdown tables for the README, from the tuned results (results/tuned.csv).

Prints and writes results/report.md:
- each method's tuned parameters and mean errors, with heading and
  inclination (tilt) error separately
- mean total error per kind of trial (motion type or disturbance type)
- each method's worst trials
- an out-of-sample check of the tuning (from results/tuning.csv): every trial
  is scored with the parameter set that is best on the other 38 trials
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ORDER = ["madgwick", "mahony", "vqf", "eskf", "eskf_gated"]
LABELS = {
    "madgwick": "Madgwick",
    "mahony": "Mahony",
    "vqf": "VQF",
    "eskf": "ESKF (ours)",
    "eskf_gated": "ESKF + gating (ours)",
}
KINDS = [
    "slow_rotation", "fast_rotation", "slow_translation", "fast_translation", "slow_combined",
    "fast_combined", "tapping", "phone_vibration", "stationary_magnet", "attached_magnet",
    "office", "mixed",
]


def kind(trial):
    return next(k for k in KINDS if k in trial)


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def leave_one_out(path):
    """Mean total RMSE per method, in-sample (TAGP) and leave-one-trial-out."""
    scores = defaultdict(lambda: defaultdict(dict))
    with open(path) as f:
        for r in csv.DictReader(f):
            scores[r["method"]][r["params"]][r["trial"]] = float(r["total"])
    result = {}
    for method, by_params in scores.items():
        trials = sorted({t for per_trial in by_params.values() for t in per_trial})
        # as in scripts/tune.py, a set that failed or missed a trial cannot win
        valid = {p: s for p, s in by_params.items() if len(s) == len(trials) and np.all(np.isfinite(list(s.values())))}
        in_sample = min(np.mean(list(s.values())) for s in valid.values())
        held_out = []
        for t in trials:
            best = min(valid, key=lambda p: np.mean([valid[p][u] for u in trials if u != t]))
            held_out.append(valid[best][t])
        result[method] = (in_sample, np.mean(held_out))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="results/tuned.csv")
    parser.add_argument("--params", default="results/tagp.json")
    parser.add_argument("--tuning", default="results/tuning.csv")
    parser.add_argument("--out", default="results/report.md")
    args = parser.parse_args()

    with open(args.csv) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("total", "heading", "inclination"):
            r[k] = float(r[k])
    tagp = json.loads(Path(args.params).read_text())
    methods = [m for m in ORDER if any(r["method"] == m for r in rows)]

    def mean(method, column="total", where=lambda r: True):
        return np.mean([r[column] for r in rows if r["method"] == method and where(r)])

    parts = ["## Tuned results\n"]
    parts.append(table(
        ["Method", "Parameters (TAGP)", "Clean trials", "Disturbed trials", "Heading", "Inclination"],
        [[LABELS[m],
          ", ".join(f"{k} = {v:g}" for k, v in tagp[m]["params"].items()),
          f"{mean(m, where=lambda r: r['disturbed'] == 'False'):.1f}°",
          f"{mean(m, where=lambda r: r['disturbed'] == 'True'):.1f}°",
          f"{mean(m, 'heading'):.1f}°",
          f"{mean(m, 'inclination'):.1f}°"] for m in methods]))

    parts.append("\n\n## Mean total error by kind of trial\n")
    kind_rows = []
    for k in KINDS:
        n = len({r["trial"] for r in rows if kind(r["trial"]) == k})
        values = [mean(m, where=lambda r: kind(r["trial"]) == k) for m in methods]
        best = int(np.argmin(values))
        cells = [f"**{v:.1f}°**" if i == best else f"{v:.1f}°" for i, v in enumerate(values)]
        kind_rows.append([k.replace("_", " "), str(n)] + cells)
    parts.append(table(["Trials", "n"] + [LABELS[m] for m in methods], kind_rows))

    parts.append("\n\n## Worst three trials per method\n")
    worst_rows = []
    for m in methods:
        mine = sorted((r for r in rows if r["method"] == m), key=lambda r: -r["total"])[:3]
        worst_rows.append([LABELS[m]] + [f"{r['trial']} ({r['total']:.1f}°)" for r in mine])
    parts.append(table(["Method", "Worst", "2nd", "3rd"], worst_rows))

    parts.append("\n\n## Out-of-sample check of the tuning (mean total error)\n")
    loo = leave_one_out(args.tuning)
    parts.append(table(
        ["Method", "Tuned on all 39 trials", "Each trial tuned on the other 38"],
        [[LABELS[m], f"{loo[m][0]:.2f}°", f"{loo[m][1]:.2f}°"] for m in methods if m in loo]))

    text = "".join(parts) + "\n"
    Path(args.out).write_text(text)
    print(text)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
