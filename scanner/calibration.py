"""Lens distortion calibration. Currently an identity passthrough stub.

TODO: implement checkerboard capture + cv2.calibrateCamera workflow.
See scanner/CALIBRATION.md for the planned procedure.
"""

import os

import cv2
import numpy as np

_DEFAULT_CALIBRATION_PATH = os.path.join(os.path.dirname(__file__), "calibration_data.npz")

_lazy_calibration = None
_lazy_loaded = False


def load_calibration(path=None):
    """Load calibration data, or return None if no calibration file exists.

    TODO: file format will be camera matrix + distortion coefficients from
    cv2.calibrateCamera, saved via np.savez (keys: camera_matrix, dist_coeffs).
    """
    if path is None:
        path = _DEFAULT_CALIBRATION_PATH
    if not os.path.exists(path):
        return None
    data = np.load(path)
    return {
        "camera_matrix": data["camera_matrix"],
        "dist_coeffs": data["dist_coeffs"],
    }


def _default_calibration():
    global _lazy_calibration, _lazy_loaded
    if not _lazy_loaded:
        _lazy_calibration = load_calibration()
        _lazy_loaded = True
    return _lazy_calibration


def undistort_frame(frame, calibration=None):
    """Remove lens distortion from a frame. Identity when no calibration exists."""
    if calibration is None:
        calibration = _default_calibration()
    if calibration is None:
        return frame
    # TODO: plug checkerboard-derived calibration in here.
    return cv2.undistort(
        frame, calibration["camera_matrix"], calibration["dist_coeffs"]
    )
