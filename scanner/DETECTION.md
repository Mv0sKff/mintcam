# Object Detection (future work)

Status: stub. `scanner.detection.detect_objects()` returns an empty list.

## Why

After stitching, detect objects/parts on the scan image to label or locate
them automatically.

## Candidate approaches (keep Pi-friendly)

- Classical cv2: thresholding + `cv2.findContours` for simple parts.
- Small model: YOLOv8n exported to ONNX, run via `cv2.dnn`.

## Where it plugs in

`scanner.detection.detect_objects(image)` is called from the stitch pipeline
or the webapp once the final stitched image is produced. Optionally per-frame
detection can be added later.

## Output format contract

Returns a list of dicts:

```python
{"label": str, "confidence": float, "bbox": (x, y, w, h)}
```

Overlay rendering idea: draw the bboxes (and labels) on a copy of the stitched
image with `cv2.rectangle` / `cv2.putText` and serve that as a preview.

## Status checklist

- [ ] TODO: pick detection approach (contours vs ONNX model)
- [ ] TODO: implement detect_objects
- [ ] TODO: wire into stitch pipeline / webapp
- [ ] TODO: render bbox overlay preview
