"""Orientation error metrics as defined in the BROAD paper.

The error quaternion is expressed in the earth frame, which lets the total
error be split into a heading part (rotation about the vertical axis, mostly a
magnetometer problem) and an inclination part (tilt, mostly an accelerometer
problem).
"""
import numpy as np

from quat import conjugate, multiply, normalize


def error_quat_earth(quat_est, quat_ref):
    return normalize(multiply(normalize(quat_est), conjugate(normalize(quat_ref))))


def total_error(q_err):
    return 2 * np.arccos(np.clip(np.abs(q_err[:, 0]), 0, 1))


def heading_error(q_err):
    return 2 * np.arctan(np.abs(q_err[:, 3] / q_err[:, 0]))


def inclination_error(q_err):
    return 2 * np.arccos(np.clip(np.sqrt(q_err[:, 0] ** 2 + q_err[:, 3] ** 2), 0, 1))


def rmse_deg(quat_est, quat_ref, mask):
    """RMSE in degrees over the samples selected by mask (NaN ground truth is skipped)."""
    q_err = error_quat_earth(quat_est, quat_ref)

    def rmse(err):
        return float(np.rad2deg(np.sqrt(np.nanmean(err[mask] ** 2))))

    return {
        "total": rmse(total_error(q_err)),
        "heading": rmse(heading_error(q_err)),
        "inclination": rmse(inclination_error(q_err)),
    }
