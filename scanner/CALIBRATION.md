# Lens Calibration (future work)

Status: identity passthrough stub. `undistort_frame()` returns frames unchanged
until a calibration file exists.

## Why

The wide-angle / close-focus lens on the scan camera distorts frames, which
causes visible seams and misalignment in the stitched image. Undistorting each
frame before compositing fixes this.

## Procedure outline

1. Print a checkerboard pattern (see the [OpenCV camera calibration pattern
   docs](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html)).
2. Generate a dedicated calibration scan gcode file (or move the printer head
   manually) so the camera sees the pattern from multiple positions/angles.
3. Capture frames or a video of the pattern.
4. Run `cv2.findChessboardCorners` over multiple views to collect image points.
5. Run `cv2.calibrateCamera` to get the camera matrix and distortion
   coefficients.
6. Save them via `np.savez` to `scanner/calibration_data.npz` with keys
   `camera_matrix` and `dist_coeffs`.
7. `scanner.calibration.undistort_frame` picks the file up automatically.

## Status checklist

- [ ] TODO: choose checkerboard dimensions and square size
- [ ] TODO: create calibration scan gcode
- [ ] TODO: capture calibration frames
- [ ] TODO: run cv2.findChessboardCorners + cv2.calibrateCamera
- [ ] TODO: save scanner/calibration_data.npz
- [ ] TODO: verify stitching seams improve with undistortion enabled
