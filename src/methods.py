"""Orientation filters under test, and a parallel runner to score them.

Every runner takes a Trial plus the filter's tunable parameters and returns the
estimated orientation as East-North-Up quaternions [w, x, y, z], one per sample.
"""
import json
import multiprocessing
import os

import numpy as np
from ahrs.filters import Madgwick, Mahony
from vqf import VQF

from broad import load_trial
from degrade import degrade
from eskf import run_eskf
from metrics import rmse_deg
from quat import multiply

# The ahrs Madgwick filter reports orientation relative to a North-West-Up earth
# frame. Rotating by +90° about the vertical axis gives BROAD's East-North-Up
# frame (checked against the ground truth; Mahony and VQF already use ENU).
NWU_TO_ENU = np.array([np.sqrt(0.5), 0.0, 0.0, np.sqrt(0.5)])


def run_madgwick(trial, gain=0.041):
    quat = Madgwick(gyr=trial.gyr, acc=trial.acc, mag=trial.mag, frequency=trial.rate, gain=gain).Q
    return multiply(NWU_TO_ENU, quat)


def run_mahony(trial, k_P=1.0, k_I=0.3):
    return Mahony(gyr=trial.gyr, acc=trial.acc, mag=trial.mag, frequency=trial.rate, k_P=k_P, k_I=k_I).Q


def run_vqf(trial, tauAcc=3.0, tauMag=9.0):
    # The real-time version. The package's offlineVQF also looks at future
    # samples, which no real-time filter can do, so it would not be a fair rival.
    gyr, acc, mag = (np.ascontiguousarray(x) for x in (trial.gyr, trial.acc, trial.mag))
    return VQF(trial.dt, tauAcc=tauAcc, tauMag=tauMag).updateBatch(gyr, acc, mag)["quat9D"]


def run_eskf_gated(trial, acc_noise=0.1, mag_noise=0.1):
    return run_eskf(trial, acc_noise, mag_noise, gating=True)


METHODS = {
    "madgwick": run_madgwick,
    "mahony": run_mahony,
    "vqf": run_vqf,
    "eskf": run_eskf,
    "eskf_gated": run_eskf_gated,
}


def evaluate(job):
    """Run one method with several parameter sets on one trial.

    job = (method, trial_path, list of parameter dicts), optionally followed by
    a dict of arguments for degrade.degrade. Returns one result row per
    parameter set. The trial is loaded here, inside the worker process, so
    only its path has to be sent between processes.
    """
    method, trial_path, param_sets, *degradation = job
    trial = load_trial(trial_path)
    if degradation:
        trial = degrade(trial, **degradation[0])
    rows = []
    for params in param_sets:
        err = rmse_deg(METHODS[method](trial, **params), trial.quat_ref, trial.movement)
        rows.append({
            "trial": trial.name,
            "disturbed": trial.disturbed,
            "method": method,
            "params": json.dumps(params, sort_keys=True),
            **({"degradation": json.dumps(degradation[0], sort_keys=True)} if degradation else {}),
            **err,
        })
    return rows


def run_parallel(jobs):
    """Evaluate jobs on all but one CPU core, yielding each job's rows as it finishes.

    The most expensive jobs (long trials, many parameter sets) are started first
    so that no core is left with a long job at the end.
    """
    jobs = sorted(jobs, key=lambda j: os.path.getsize(j[1]) * len(j[2]), reverse=True)
    with multiprocessing.Pool(max(1, os.cpu_count() - 1)) as pool:
        yield from pool.imap_unordered(evaluate, jobs)
