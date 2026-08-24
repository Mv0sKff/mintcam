"""Object detection on stitched scan images. Stub for now.

TODO: implement detection. See scanner/DETECTION.md for planned approaches.
Called post-stitch on the final image (optionally per-frame later).
"""


def detect_objects(image):
    """Detect objects in an image.

    Planned return value: list of dicts, each
    {"label": str, "confidence": float, "bbox": (x, y, w, h)}.
    """
    # TODO: run detection (classical cv2 contours or a small DNN model).
    return []
