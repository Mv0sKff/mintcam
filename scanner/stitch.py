"""Stitch a scanning-microscope raster video into one image.

Usage: python -m scanner.stitch input.mp4 -o output.jpg [options]
"""

import argparse
import sys

import cv2
import numpy as np

try:
    from scanner.calibration import undistort_frame
except ImportError:
    from calibration import undistort_frame

DEFAULT_MAX_FRAMES = 200
JPEG_QUALITY = 95


def log(msg, verbose):
    if verbose:
        print(msg)


def extract_frames(video_path, max_frames, grid_rows=None, grid_cols=None, verbose=False):
    """Sample frames evenly across the video, at most max_frames (or grid size)."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        raise RuntimeError(f"no frames in video: {video_path}")

    n = min(max_frames, total)
    if grid_rows and grid_cols:
        n = min(n, grid_rows * grid_cols)
    indices = np.linspace(0, total - 1, n).round().astype(int).tolist()

    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if ok and frame is not None:
            frames.append(frame)
    cap.release()
    log(f"extracted {len(frames)} frames (of {total} in video)", verbose)
    if not frames:
        raise RuntimeError(f"could not read any frames from: {video_path}")
    return frames


def estimate_grid(n):
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))
    return rows, cols


def grid_positions(n, rows, cols):
    """Boustrophedon order: even rows left->right, odd rows right->left."""
    pos = []
    for i in range(n):
        row = i // cols
        col = (i % cols) if row % 2 == 0 else (cols - 1 - (i % cols))
        pos.append((row, col))
    return pos


def stitch_grid(frames, rows, cols, overlap, verbose=False):
    """Composite frames onto a canvas in boustrophedon grid order."""
    if rows * cols < len(frames):
        raise RuntimeError(
            f"grid {rows}x{cols} too small for {len(frames)} frames"
        )

    heights = [f.shape[0] for f in frames]
    widths = [f.shape[1] for f in frames]
    th, tw = int(np.median(heights)), int(np.median(widths))
    resized = [
        f if f.shape[:2] == (th, tw) else cv2.resize(f, (tw, th)) for f in frames
    ]

    crop_x = int(tw * overlap / 2)
    crop_y = int(th * overlap / 2)
    if crop_x * 2 >= tw or crop_y * 2 >= th:
        raise RuntimeError(f"overlap {overlap} too large for tile size {tw}x{th}")

    canvas = np.zeros((th * rows, tw * cols, 3), dtype=np.uint8)
    for frame, (row, col) in zip(resized, grid_positions(len(resized), rows, cols)):
        tile = frame[crop_y : th - crop_y, crop_x : tw - crop_x]
        y, x = row * th, col * tw
        canvas[y + crop_y : y + crop_y + tile.shape[0],
               x + crop_x : x + crop_x + tile.shape[1]] = tile
    log(f"grid composite: {len(resized)} tiles on {cols * tw}x{rows * th} canvas", verbose)
    return canvas


def stitch_stitcher(frames, verbose=False):
    stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
    status, pano = stitcher.stitch(frames)
    if status != cv2.Stitcher_OK:
        raise RuntimeError(f"cv2.Stitcher failed with status {status}")
    log(f"stitcher composite: {len(frames)} frames", verbose)
    return pano


def validate(image):
    if image is None or image.size == 0:
        raise RuntimeError("stitching produced an empty image")
    h, w = image.shape[:2]
    if h < 2 or w < 2 or h > 65500 or w > 65500:
        raise RuntimeError(f"stitched image has insane size {w}x{h}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="scanner.stitch")
    parser.add_argument("input", help="input video path")
    parser.add_argument("-o", "--output", default="stitched_output.jpg")
    parser.add_argument("--grid-rows", type=int, default=None)
    parser.add_argument("--grid-cols", type=int, default=None)
    parser.add_argument("--overlap", type=float, default=0.2)
    parser.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    parser.add_argument("--method", choices=["auto", "grid", "stitcher"], default="auto")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not 0.0 <= args.overlap < 1.0:
        parser.error("--overlap must be in [0, 1)")
    if (args.grid_rows is None) != (args.grid_cols is None):
        parser.error("--grid-rows and --grid-cols must be given together")

    try:
        frames = extract_frames(
            args.input, args.max_frames, args.grid_rows, args.grid_cols, args.verbose
        )
        frames = [undistort_frame(f) for f in frames]

        rows = cols = None
        if args.method in ("auto", "grid"):
            if args.grid_rows and args.grid_cols:
                rows, cols = args.grid_rows, args.grid_cols
            else:
                rows, cols = estimate_grid(len(frames))
                log(f"auto-estimated grid: {rows}x{cols}", args.verbose)

        result = None
        if args.method == "stitcher":
            result = stitch_stitcher(frames, args.verbose)
        elif args.method == "grid":
            result = stitch_grid(frames, rows, cols, args.overlap, args.verbose)
        else:
            try:
                result = stitch_grid(frames, rows, cols, args.overlap, args.verbose)
                validate(result)
            except Exception as exc:
                log(f"grid method failed ({exc}), falling back to stitcher", args.verbose)
                result = stitch_stitcher(frames, args.verbose)
        validate(result)

        if not cv2.imwrite(args.output, result, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]):
            raise RuntimeError(f"failed to write output: {args.output}")
        h, w = result.shape[:2]
        print(f"wrote {args.output} ({w}x{h})")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
