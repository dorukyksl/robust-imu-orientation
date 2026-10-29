"""Make a recorded trial look as if it came from a cheaper IMU.

Three kinds of degradation, which can be combined:
- noise: total sensor noise multiplied by a factor, by adding white noise
- rate:  lower sampling rate; blocks of samples are averaged, as a sensor's
         own low-pass filter would do, then only one sample per block is kept
- bias:  a constant gyroscope offset (deg/s) in a random direction
"""
import dataclasses
import math
import zlib

import numpy as np

# Noise of the recorded IMU while lying still: median over the 39 trials of the
# per-axis standard deviation during the rest phase.
REST_NOISE = {"gyr": math.radians(0.128), "acc": 0.0547, "mag": 0.696}

# one factor at a time; the first value of each is the sensor as recorded
SWEEPS = {
    "noise": [1, 2, 5, 10, 20],        # total noise, multiple of the recorded IMU's
    "rate": [None, 100, 50, 25],       # Hz; None = as recorded (286 Hz)
    "bias": [0, 0.5, 1, 2, 5],         # extra gyroscope bias, deg/s
}

# all three together
LADDER = {
    "As recorded": {"noise": 1, "rate": None, "bias": 0},
    "Good consumer": {"noise": 2, "rate": 100, "bias": 0.5},
    "Cheap": {"noise": 5, "rate": 50, "bias": 1},
    "Very cheap": {"noise": 10, "rate": 25, "bias": 2},
}


def conditions():
    """Every distinct degradation to run, as keyword arguments for degrade()."""
    found = []
    for factor, values in SWEEPS.items():
        for value in values:
            found.append({**LADDER["As recorded"], factor: value})
    found.extend(LADDER.values())
    unique = []
    for c in found:
        if c not in unique:
            unique.append(c)
    return unique


def degrade(trial, noise=1.0, rate=None, bias=0.0):
    # the same trial always gets the same random numbers, in every process
    rng = np.random.default_rng(zlib.crc32(trial.name.encode()))
    gyr, acc, mag = trial.gyr.copy(), trial.acc.copy(), trial.mag.copy()
    quat_ref, movement, new_rate = trial.quat_ref, trial.movement, trial.rate

    if noise > 1.0:
        extra = math.sqrt(noise ** 2 - 1.0)
        gyr += rng.normal(0.0, extra * REST_NOISE["gyr"], gyr.shape)
        acc += rng.normal(0.0, extra * REST_NOISE["acc"], acc.shape)
        mag += rng.normal(0.0, extra * REST_NOISE["mag"], mag.shape)

    if bias > 0.0:
        direction = rng.normal(size=3)
        gyr += math.radians(bias) * direction / np.linalg.norm(direction)

    if rate is not None and rate < trial.rate:
        k = round(trial.rate / rate)
        n = len(gyr) // k * k
        gyr, acc, mag = (x[:n].reshape(-1, k, 3).mean(axis=1) for x in (gyr, acc, mag))
        # the estimate after a block belongs to the block's last sample
        quat_ref, movement = quat_ref[k - 1:n:k], movement[k - 1:n:k]
        new_rate = trial.rate / k

    return dataclasses.replace(trial, rate=new_rate, gyr=gyr, acc=acc, mag=mag,
                               quat_ref=quat_ref, movement=movement)
