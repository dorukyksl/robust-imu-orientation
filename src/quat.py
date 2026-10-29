"""Minimal quaternion helpers.

Convention (same as the BROAD dataset):
- quaternions are stored as [w, x, y, z]
- Hamilton product
- an orientation quaternion q rotates sensor-frame vectors into the ENU earth frame
"""
import numpy as np


def multiply(q1, q2):
    """Hamilton product q1 * q2. Works on single quaternions or (N, 4) arrays."""
    q1 = np.asarray(q1, float)
    q2 = np.asarray(q2, float)
    w1, x1, y1, z1 = np.moveaxis(q1, -1, 0)
    w2, x2, y2, z2 = np.moveaxis(q2, -1, 0)
    return np.stack([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ], axis=-1)


def conjugate(q):
    """Inverse of a unit quaternion."""
    q = np.array(q, float)
    q[..., 1:] *= -1
    return q


def normalize(q):
    q = np.asarray(q, float)
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def from_rotation_vector(rv):
    """Quaternion for a rotation of |rv| radians around the axis rv / |rv|."""
    rv = np.asarray(rv, float)
    angle = np.linalg.norm(rv, axis=-1, keepdims=True)
    half = angle / 2
    # sin(x)/x is well defined at x = 0; np.sinc(x / pi) gives exactly that
    scale = 0.5 * np.sinc(half / np.pi)
    return np.concatenate([np.cos(half), scale * rv], axis=-1)
