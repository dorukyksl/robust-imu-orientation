"""Step 4: how do the methods cope with a cheaper sensor?

The recorded data are made worse (see src/degrade.py) in three ways, one at a
time, and all together along a ladder from the recorded IMU to a very cheap one
(SWEEPS and LADDER in src/degrade.py):
- more noise
- lower sampling rate
- more gyroscope bias

Every method keeps the parameters tuned on the original data (results/tagp.json,
from scripts/tune.py): the question is how robust each one is out of the box,
not how well it could be retuned for a new sensor.

Results go to results/cheap_sensor.csv, one row per condition, trial and method.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from degrade import LADDER, conditions  # noqa: E402
from methods import METHODS, run_parallel  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/broad_hdf5")
    parser.add_argument("--params", default="results/tagp.json")
    parser.add_argument("--out", default="results/cheap_sensor.csv")
    args = parser.parse_args()

    with open(args.params) as f:
        params = {method: best["params"] for method, best in json.load(f).items()}
    trial_paths = sorted(str(p) for p in Path(args.data).glob("*.hdf5"))
    conds = conditions()
    jobs = [(method, path, [params[method]], cond)
            for cond in conds for path in trial_paths for method in METHODS]
    print(f"{len(jobs)} jobs: {len(conds)} conditions x {len(trial_paths)} trials x {len(METHODS)} methods",
          flush=True)

    rows = []
    for i, result in enumerate(run_parallel(jobs), 1):
        rows.extend(result)
        if i % 100 == 0 or i == len(jobs):
            print(f"[{i}/{len(jobs)}]", flush=True)
    order = list(METHODS)
    rows.sort(key=lambda r: (r["degradation"], r["trial"], order.index(r["method"])))

    out = Path(args.out)
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out}\n")

    print("Mean total RMSE (°) along the ladder")
    print(f"{'':16s}" + "".join(f"{m:>12s}" for m in METHODS))
    for name, cond in LADDER.items():
        key = json.dumps(cond, sort_keys=True)
        means = [np.mean([r["total"] for r in rows if r["degradation"] == key and r["method"] == m])
                 for m in METHODS]
        print(f"{name:16s}" + "".join(f"{v:12.1f}" for v in means))


if __name__ == "__main__":
    main()
