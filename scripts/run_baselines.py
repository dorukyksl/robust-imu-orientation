"""Run orientation filters on all BROAD trials.

Methods (implemented in src/methods.py):
- madgwick:   Madgwick filter from the ahrs package
- mahony:     Mahony filter from the ahrs package
- vqf:        VQF (Laidig & Seel, 2023), real-time version, from the vqf package
- eskf:       our error-state Kalman filter (src/eskf.py)
- eskf_gated: the same, with magnetic disturbance gating

By default every method uses its library's default parameters. With
--params results/tagp.json each method uses the parameter set found by
scripts/tune.py instead.

The errors are written to a CSV file, one row per trial and method, so plotting
does not need to re-run the filters.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from methods import METHODS, run_parallel  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/broad_hdf5")
    parser.add_argument("--params", help="JSON file from scripts/tune.py; library defaults if omitted")
    parser.add_argument("--out", default="results/baselines.csv")
    parser.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    args = parser.parse_args()

    params = {}
    if args.params:
        with open(args.params) as f:
            params = {method: best["params"] for method, best in json.load(f).items()}

    trial_paths = sorted(str(p) for p in Path(args.data).glob("*.hdf5"))
    jobs = [(method, path, [params.get(method, {})]) for path in trial_paths for method in args.methods]
    rows = []
    for result in run_parallel(jobs):
        rows.extend(result)
    order = args.methods
    rows.sort(key=lambda r: (r["trial"], order.index(r["method"])))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out}")

    print("\nMean total RMSE (°)       clean  disturbed")
    for method in args.methods:
        clean = np.mean([r["total"] for r in rows if r["method"] == method and not r["disturbed"]])
        dist = np.mean([r["total"] for r in rows if r["method"] == method and r["disturbed"]])
        print(f"{method:24s} {clean:6.1f}  {dist:9.1f}")


if __name__ == "__main__":
    main()
