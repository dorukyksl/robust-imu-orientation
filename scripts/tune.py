"""Step 3: fair tuning of every method, including our own.

For each method, find the one parameter set that gives the lowest mean total
RMSE over all 39 trials. The BROAD paper calls this TAGP ("trial-agnostic good
parameters"): a single setting that has to work everywhere, as it would in a
real product.

Fairness: every method is searched over a grid of similar size, scored by the
same objective, on the same data. The search is in-sample (tuned and scored on
the same 39 trials), exactly as in the BROAD paper, and equally so for every
method.

Every (method, parameters, trial) result is written to results/tuning.csv and
the best set per method to results/tagp.json. With --methods only those methods
are re-run; the results of the others are kept.
"""
import argparse
import csv
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from methods import METHODS, run_parallel  # noqa: E402

GRIDS = {
    "madgwick": {"gain": [0.003, 0.005, 0.007, 0.01, 0.015, 0.02, 0.03, 0.05, 0.07, 0.1, 0.2, 0.3]},
    # ahrs rejects k_I = 0, so the smallest integral gain is 0.0001
    "mahony": {"k_P": [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0], "k_I": [0.0001, 0.001, 0.01, 0.03, 0.1, 0.3]},
    # time constants in seconds; VQF's other parameters stay at their defaults
    "vqf": {"tauAcc": [0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0], "tauMag": [1.0, 3.0, 9.0, 20.0, 50.0]},
    # measurement noise (smaller = more trust); all other settings are fixed in src/eskf.py
    "eskf": {"acc_noise": [0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0], "mag_noise": [0.03, 0.1, 0.3, 1.0, 3.0, 10.0]},
    "eskf_gated": {"acc_noise": [0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0], "mag_noise": [0.03, 0.1, 0.3, 1.0, 3.0, 10.0]},
}

FIELDS = ["trial", "disturbed", "method", "params", "total", "heading", "inclination"]


def param_sets(grid):
    names = list(grid)
    return [dict(zip(names, values)) for values in itertools.product(*grid.values())]


def read_rows(path):
    if not path.exists():
        return []
    with open(path) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["disturbed"] = r["disturbed"] == "True"
        for key in ("total", "heading", "inclination"):
            r[key] = float(r[key])
    return rows


def best_params(rows, method, n_trials):
    """Parameter set with the lowest mean total RMSE over all trials."""
    by_params = defaultdict(list)
    for r in rows:
        if r["method"] == method:
            by_params[r["params"]].append(r)
    scores = {}
    for params, results in by_params.items():
        totals = [r["total"] for r in results]
        # a set that failed on any trial (NaN) or missed one cannot win
        scores[params] = np.mean(totals) if len(totals) == n_trials and np.all(np.isfinite(totals)) else np.inf
    best = min(scores, key=scores.get)
    results = by_params[best]
    return {
        "params": json.loads(best),
        "mean_total": scores[best],
        "mean_clean": np.mean([r["total"] for r in results if not r["disturbed"]]),
        "mean_disturbed": np.mean([r["total"] for r in results if r["disturbed"]]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/broad_hdf5")
    parser.add_argument("--out", default="results")
    parser.add_argument("--methods", nargs="+", default=list(GRIDS), choices=list(GRIDS))
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    trial_paths = sorted(str(p) for p in Path(args.data).glob("*.hdf5"))

    jobs = [(m, path, param_sets(GRIDS[m])) for m in args.methods for path in trial_paths]
    print(f"{len(jobs)} jobs: {', '.join(f'{m} {len(param_sets(GRIDS[m]))} sets' for m in args.methods)}"
          f" x {len(trial_paths)} trials", flush=True)
    new_rows = []
    for i, rows in enumerate(run_parallel(jobs), 1):
        new_rows.extend(rows)
        print(f"[{i:3d}/{len(jobs)}] {rows[0]['method']:9s} {rows[0]['trial']}", flush=True)

    # keep earlier results of methods that were not re-run
    csv_path = out / "tuning.csv"
    rows = [r for r in read_rows(csv_path) if r["method"] not in args.methods] + new_rows
    rows.sort(key=lambda r: (r["method"], r["params"], r["trial"]))
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    json_path = out / "tagp.json"
    tagp = json.loads(json_path.read_text()) if json_path.exists() else {}
    for method in args.methods:
        tagp[method] = best_params(rows, method, len(trial_paths))
    tagp = {m: tagp[m] for m in METHODS if m in tagp}
    json_path.write_text(json.dumps(tagp, indent=2) + "\n")
    print(f"\nSaved {csv_path} and {json_path}\n")

    print("Method     best parameters                      clean  disturbed")
    for method in args.methods:
        best = tagp[method]
        text = ", ".join(f"{k}={v:g}" for k, v in best["params"].items())
        print(f"{method:10s} {text:36s} {best['mean_clean']:5.1f}° {best['mean_disturbed']:8.1f}°")
        for name, value in best["params"].items():
            if value in (GRIDS[method][name][0], GRIDS[method][name][-1]):
                print(f"  warning: {name}={value:g} is at the edge of the grid; widen the grid")


if __name__ == "__main__":
    main()
