#!/usr/bin/env bash
# Reproduce every number and figure in the README from scratch.
# Takes about an hour on a 14-core laptop; the filters run in parallel on all
# but one core. Set PYTHON to use another interpreter than .venv/bin/python.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-.venv/bin/python}

$PY scripts/download_data.py

# Step 1: gyroscope only
$PY scripts/gyro_only.py

# Step 2: standard filters with their library defaults
$PY scripts/run_baselines.py --methods madgwick mahony vqf
$PY scripts/plot_baselines.py

# Step 3: fair tuning of every method, then all methods with their tuned parameters
$PY scripts/tune.py
$PY scripts/run_baselines.py --params results/tagp.json --out results/tuned.csv
$PY scripts/plot_baselines.py --csv results/tuned.csv --out results/tuned.png \
    --title "All methods, each with its best single parameter set (TAGP)"

# Step 4: cheaper sensors
$PY scripts/cheap_sensor.py
$PY scripts/plot_cheap_sensor.py

# Tables for the README
$PY scripts/report.py
