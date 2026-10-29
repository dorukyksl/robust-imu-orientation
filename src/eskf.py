"""Error-state Kalman filter (ESKF) for orientation and gyroscope bias.

The filter keeps a best guess (the nominal state) and runs a Kalman filter on
the small error of that guess:

- nominal state: orientation q (sensor to East-North-Up, [w, x, y, z]) and
  gyroscope bias b (rad/s)
- error state:   small rotation (rad, sensor frame) and bias error (rad/s),
  with a 6x6 covariance P that says how unsure the filter is about each

Every sample:
1. predict:       turn q by the bias-corrected gyroscope reading; P grows
2. rest update:   if the sensor has been still for a while, the gyroscope
                  should read zero, so whatever it reads is bias (a "zero
                  angular rate update", as in inertial navigation). Once the
                  bias has been measured at rest, it is held fixed in motion:
                  the accelerometer and magnetometer then correct only the
                  orientation. Learning the bias from them in motion made it
                  wander by up to 0.4°/s on BROAD, and the heading drifted
                  with it. Before the first rest, they may still set the bias
3. accelerometer: compare the measured "up" direction with the predicted one;
                  this corrects tilt. At rest the raw reading is gravity only
                  and is trusted a lot; in motion the reading is first
                  averaged over a few seconds in the earth frame, where the
                  sensor's own acceleration cancels out
4. magnetometer:  compare the measured heading with the predicted one; this
                  corrects heading only, so a disturbed magnetic field can never
                  tilt the estimate

With gating=True, the magnetometer is checked before it is used:
- skipped while the field's strength or dip angle is far from the Earth field
  seen before (a magnet or steel is nearby), and until it has looked right
  again for a short while
- down-weighted when its innovation (measurement minus prediction) is larger
  than the filter's own uncertainty can explain (chi-square test)
"""
import math

import numpy as np
from scipy.spatial.transform import Rotation

# Fixed sensor noise values, not tuned. The gyroscope noise is about the
# standard deviation measured while the IMU lies still at the start of a trial.
GYR_NOISE = math.radians(0.15)        # rad/s, per sample
ACC_REST_NOISE = 0.01                 # accelerometer noise when at rest: then it measures gravity only
ACC_LP_TAU = 3.0                      # s, averaging time for the accelerometer in motion (VQF's default)
BIAS_WALK = math.radians(0.01)        # rad/s per sqrt(s): how fast the bias may wander
INIT_ANGLE_STD = math.radians(5.0)    # rad
INIT_BIAS_STD = math.radians(1.0)     # rad/s
INIT_TIME = 0.5                       # s at the start used for the initial orientation

# Rest detection, fixed, not tuned (similar to VQF's defaults)
REST_LP_TAU = 0.5                     # s, low-pass filter time constant
REST_GYR_TH = math.radians(2.0)       # rad/s, max gyro deviation and max low-passed rate
REST_ACC_TH = 0.5                     # m/s^2, max acc deviation from its low-passed value
REST_MIN_T = 1.5                      # s the sensor must be still before it counts as rest

# Magnetometer gating, fixed, not tuned (VQF's published defaults where VQF has the same check)
MAG_LP_TAU = 0.05                     # s, low-pass on field strength and dip, against sensor noise
MAG_NORM_TH = 0.1                     # skip when the field strength differs from the reference by more than 10%
MAG_DIP_TH = math.radians(10.0)       # ... or its dip angle by more than 10°
MAG_MIN_GOOD = 0.5                    # s the field must look right before it is used again
MAG_REF_TAU = 20.0                    # s, how slowly the reference follows accepted readings
MAG_MAX_REJECT = 60.0                 # s, after this long without updates, accept the new field
CHI2_MAG = 6.63                       # 99% chi-square value, 1 degree of freedom


def initial_quat(acc, mag):
    """Orientation from one accelerometer and magnetometer reading at rest."""
    up = acc / np.linalg.norm(acc)
    east = np.cross(mag, up)
    east /= np.linalg.norm(east)
    north = np.cross(up, east)
    # rows are the earth axes written in sensor coordinates
    return Rotation.from_matrix(np.vstack([east, north, up])).as_quat(scalar_first=True)


def _turn(q, rv):
    """q * Exp(rv), normalized: q turned by the small rotation vector rv (sensor frame).

    Same as quat.multiply(q, quat.from_rotation_vector(rv)), written out with
    plain floats because it runs millions of times.
    """
    half = 0.5 * math.sqrt(rv[0] * rv[0] + rv[1] * rv[1] + rv[2] * rv[2])
    s = 0.5 if half < 1e-12 else math.sin(half) / (2.0 * half)
    w2, x2, y2, z2 = math.cos(half), s * rv[0], s * rv[1], s * rv[2]
    w1, x1, y1, z1 = q
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (w / n, x / n, y / n, z / n)


def _matrix(q):
    """Rotation matrix that turns sensor-frame vectors into the earth frame."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def _skew(v):
    """Matrix form of the cross product: _skew(a) @ b == np.cross(a, b)."""
    return np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])


def _dip(mag_earth):
    """Angle between the magnetic field and the horizontal plane, positive downwards."""
    return math.atan2(-mag_earth[2], math.hypot(mag_earth[0], mag_earth[1]))


def run_eskf(trial, acc_noise=0.1, mag_noise=0.1, gating=False):
    """Estimate orientation for a whole trial.

    acc_noise: how much the accelerometer's "up" direction is trusted (smaller = more), unitless
    mag_noise: how much the magnetometer's heading is trusted (smaller = more), rad
    """
    dt = trial.dt
    n_init = max(1, int(INIT_TIME * trial.rate))
    q = tuple(initial_quat(trial.acc[:n_init].mean(axis=0), trial.mag[:n_init].mean(axis=0)))
    b = np.zeros(3)
    P = np.diag([INIT_ANGLE_STD ** 2] * 3 + [INIT_BIAS_STD ** 2] * 3)
    Q = np.diag([(GYR_NOISE * dt) ** 2] * 3 + [BIAS_WALK ** 2 * dt] * 3)
    R_rest = GYR_NOISE ** 2 * np.eye(3)
    R_acc = acc_noise ** 2 * np.eye(3)
    R_acc_rest = ACC_REST_NOISE ** 2 * np.eye(3)
    r_mag = mag_noise ** 2
    F = np.eye(6)
    F[:3, 3:] = -dt * np.eye(3)
    I6 = np.eye(6)

    # In motion the accelerometer measures gravity plus the sensor's own
    # acceleration. Averaged in the earth frame over a few seconds, the own
    # acceleration nearly cancels (it only changes the velocity, which stays
    # bounded) and gravity remains (the idea behind VQF, Laidig & Seel 2023).
    acc_earth = _matrix(q) @ trial.acc[:n_init].mean(axis=0)
    acc_alpha = dt / ACC_LP_TAU
    e_up = np.array([0.0, 0.0, 1.0])
    H_up = _skew(e_up)

    rest_alpha = dt / REST_LP_TAU
    gyr_lp, acc_lp = trial.gyr[0].copy(), trial.acc[0].copy()
    still_for = 0.0
    rested = False  # has the bias been measured at rest yet?

    mag_ref = _matrix(q) @ trial.mag[:n_init].mean(axis=0)
    ref_norm, ref_dip = np.linalg.norm(mag_ref), _dip(mag_ref)
    norm_lp, dip_lp = ref_norm, ref_dip
    lp_alpha = dt / MAG_LP_TAU
    ref_alpha = dt / MAG_REF_TAU
    rejected_for = 0.0
    good_for = MAG_MIN_GOOD

    def correct(dx, P_new):
        nonlocal q, b, P, acc_earth
        # the averaged acceleration turns with the corrected earth frame
        acc_earth = acc_earth + np.cross(_matrix(q) @ dx[:3], acc_earth)
        q = _turn(q, dx[:3])
        b = b + dx[3:]
        P = 0.5 * (P_new + P_new.T)

    out = np.empty((len(trial.gyr), 4))
    for i, (gyr, acc, mag) in enumerate(zip(trial.gyr, trial.acc, trial.mag)):
        # 1. predict
        step = (gyr - b) * dt
        q = _turn(q, step)
        F[:3, :3] = np.eye(3) - _skew(step)
        P = F @ P @ F.T + Q

        # 2. rest: the gyroscope should read zero, so its reading is the bias
        gyr_lp += rest_alpha * (gyr - gyr_lp)
        acc_lp += rest_alpha * (acc - acc_lp)
        # the rate is checked after removing the bias estimate, so that a large
        # uncalibrated bias does not hide the rest
        still = (np.linalg.norm(gyr - gyr_lp) < REST_GYR_TH and np.linalg.norm(gyr_lp - b) < REST_GYR_TH
                 and np.linalg.norm(acc - acc_lp) < REST_ACC_TH)
        still_for = still_for + dt if still else 0.0
        at_rest = still_for >= REST_MIN_T
        rested = rested or at_rest
        hold_bias = rested and not at_rest
        if at_rest:
            S = P[3:, 3:] + R_rest
            K = np.linalg.solve(S, P[3:, :]).T
            KH = np.zeros((6, 6))
            KH[:, 3:] = K
            correct(K @ (gyr - b), (I6 - KH) @ P)

        # 3. accelerometer: measured vs predicted "up"
        Rm = _matrix(q)
        acc_earth += acc_alpha * (Rm @ acc - acc_earth)
        if at_rest:
            # still: the raw reading is gravity only (sensor coordinates)
            up = Rm[2]
            y = acc / np.linalg.norm(acc) - up
            H = _skew(up)
            R = R_acc_rest
        else:
            # moving: the averaged reading in the earth frame should point up
            y = acc_earth / np.linalg.norm(acc_earth) - e_up
            H = H_up @ Rm
            R = R_acc
        PHt = P[:, :3] @ H.T
        S = H @ PHt[:3] + R
        K = np.linalg.solve(S, PHt.T).T
        if hold_bias:
            K[3:] = 0.0
        KH = np.zeros((6, 6))
        KH[:, :3] = K @ H
        # Joseph form: P stays right for any gain, also one with the bias rows zeroed
        A = I6 - KH
        correct(K @ y, A @ P @ A.T + K @ R @ K.T)

        # 4. magnetometer: heading error, as a rotation about the earth's vertical
        Rm = _matrix(q)
        mag_earth = Rm @ mag
        y = math.atan2(mag_earth[0], mag_earth[1])
        h = Rm[2]
        r = r_mag
        use = True
        if gating:
            norm_lp += lp_alpha * (np.linalg.norm(mag_earth) - norm_lp)
            dip_lp += lp_alpha * (_dip(mag_earth) - dip_lp)
            looks_right = abs(norm_lp / ref_norm - 1.0) < MAG_NORM_TH and abs(dip_lp - ref_dip) < MAG_DIP_TH
            good_for = good_for + dt if looks_right else 0.0
            # a single reading that happens to pass is not trusted; the field has
            # to look right for a while (found on the attached-magnet trials)
            use = good_for >= MAG_MIN_GOOD
            if use:
                rejected_for = 0.0
                ref_norm += ref_alpha * (norm_lp - ref_norm)
                ref_dip += ref_alpha * (dip_lp - ref_dip)
                nis = y * y / (h @ P[:3, :3] @ h + r)
                if nis > CHI2_MAG:
                    r = r_mag * (nis / CHI2_MAG)
            else:
                rejected_for += dt
                if rejected_for > MAG_MAX_REJECT:
                    # the field has been "wrong" for a long time: it is the new normal
                    ref_norm, ref_dip, rejected_for = norm_lp, dip_lp, 0.0
        if use:
            k = P[:, :3] @ h / (h @ P[:3, :3] @ h + r)
            if hold_bias:
                k[3:] = 0.0
            A = I6.copy()
            A[:, :3] -= np.outer(k, h)
            correct(k * y, A @ P @ A.T + r * np.outer(k, k))

        out[i] = q
    return out
