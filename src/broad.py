"""Loading trials from the BROAD dataset (Laidig et al., 2021, CC BY 4.0).

Each HDF5 file holds one recording: IMU measurements plus optical motion
capture ground truth, sampled at about 286 Hz.
"""
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np


@dataclass
class Trial:
    name: str
    rate: float              # sampling rate in Hz
    gyr: np.ndarray          # (N, 3) angular rate, rad/s
    acc: np.ndarray          # (N, 3) acceleration, m/s^2
    mag: np.ndarray          # (N, 3) magnetic field, uT
    quat_ref: np.ndarray     # (N, 4) ground truth orientation, NaN where markers were lost
    movement: np.ndarray     # (N,) True during the phase used for scoring

    @property
    def dt(self):
        return 1.0 / self.rate

    @property
    def time(self):
        return np.arange(len(self.gyr)) * self.dt

    @property
    def rest(self):
        """Samples before the first movement, when the IMU lies still."""
        first_move = int(np.argmax(self.movement))
        return slice(0, first_move)

    @property
    def disturbed(self):
        return "_disturbed_" in self.name


def load_trial(path):
    path = Path(path)
    with h5py.File(path, "r") as f:
        return Trial(
            name=path.stem,
            rate=float(f.attrs["sampling_rate"]),
            gyr=f["imu_gyr"][()],
            acc=f["imu_acc"][()],
            mag=f["imu_mag"][()],
            quat_ref=f["opt_quat"][()],
            movement=f["movement"][()].astype(bool),
        )


def load_all(data_dir):
    return [load_trial(p) for p in sorted(Path(data_dir).glob("*.hdf5"))]
