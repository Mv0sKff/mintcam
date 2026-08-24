#!/usr/bin/env python3
"""G-code generator for the mintcam "scanning microscope" feature.

Generates a boustrophedon (snake / square-wave) raster scan pattern for an
Ender 5 Plus (or compatible Marlin printer) with a camera mounted on the
print head. The head moves back and forth over the scan area while a video
is recorded. Pure motion only: no heating, no extrusion, no fans.

Runnable both as:
    python -m scanner.gcode_generator -o out.gcode
and:
    python scanner/gcode_generator.py -o out.gcode
"""

import argparse
import datetime
import math
import sys

# Camera / print head distance from the print bed during the scan (mm).
# Adjust to the physical mounting height of your camera.
CAMERA_HEIGHT_MM = 120.0


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a boustrophedon (snake) raster scan G-code pattern for "
            "the mintcam scanning microscope. Pure motion, no heating/extrusion."
        )
    )
    parser.add_argument(
        "--output", "-o",
        default="scan_pattern.gcode",
        help="Output file path (default: scan_pattern.gcode)",
    )
    parser.add_argument(
        "--bed-width",
        type=float,
        default=350.0,
        help="Bed width (X) in mm (default: 350)",
    )
    parser.add_argument(
        "--bed-depth",
        type=float,
        default=350.0,
        help="Bed depth (Y) in mm (default: 350)",
    )
    parser.add_argument(
        "--scan-x-min",
        type=float,
        default=None,
        help="Scan area minimum X in mm (default: 20)",
    )
    parser.add_argument(
        "--scan-x-max",
        type=float,
        default=None,
        help="Scan area maximum X in mm (default: bed_width - 20)",
    )
    parser.add_argument(
        "--scan-y-min",
        type=float,
        default=None,
        help="Scan area minimum Y in mm (default: 20)",
    )
    parser.add_argument(
        "--scan-y-max",
        type=float,
        default=None,
        help="Scan area maximum Y in mm (default: bed_depth - 20)",
    )
    parser.add_argument(
        "--line-spacing",
        type=float,
        default=20.0,
        help="Distance between scan lines in mm (default: 20.0)",
    )
    parser.add_argument(
        "--overlap",
        type=float,
        default=None,
        help=(
            "Informational only: camera field-of-view overlap in percent. "
            "Line spacing is the primary control; this value is only echoed "
            "in the header comments if given."
        ),
    )
    parser.add_argument(
        "--feedrate",
        type=float,
        default=3000.0,
        help="Scan move speed in mm/min (default: 3000)",
    )
    parser.add_argument(
        "--travel-feedrate",
        type=float,
        default=6000.0,
        help="Feedrate for travel/positioning moves in mm/min (default: 6000)",
    )
    parser.add_argument(
        "--dwell-ms",
        type=int,
        default=100,
        help="Dwell (G4 P) in ms at the end of each scan line (default: 100)",
    )
    parser.add_argument(
        "--camera-height",
        type=float,
        default=CAMERA_HEIGHT_MM,
        help="Z height during scan in mm (default: %(default)s)",
    )
    return parser


def validate_args(args, parser):
    """Validate scan geometry; abort with a clear message on invalid input."""
    # Resolve defaults that depend on bed size.
    if args.scan_x_min is None:
        args.scan_x_min = 20.0
    if args.scan_x_max is None:
        args.scan_x_max = args.bed_width - 20.0
    if args.scan_y_min is None:
        args.scan_y_min = 20.0
    if args.scan_y_max is None:
        args.scan_y_max = args.bed_depth - 20.0

    if args.bed_width <= 0 or args.bed_depth <= 0:
        parser.error("bed dimensions must be positive")
    if args.line_spacing <= 0:
        parser.error(
            "line spacing must be > 0 (got %s)" % args.line_spacing
        )
    if not args.scan_x_min < args.scan_x_max:
        parser.error(
            "scan-x-min must be < scan-x-max (got %s >= %s)"
            % (args.scan_x_min, args.scan_x_max)
        )
    if not args.scan_y_min < args.scan_y_max:
        parser.error(
            "scan-y-min must be < scan-y-max (got %s >= %s)"
            % (args.scan_y_min, args.scan_y_max)
        )
    if args.scan_x_min < 0 or args.scan_x_max > args.bed_width:
        parser.error(
            "scan X bounds (%.3f..%.3f) must be within bed width 0..%.3f"
            % (args.scan_x_min, args.scan_x_max, args.bed_width)
        )
    if args.scan_y_min < 0 or args.scan_y_max > args.bed_depth:
        parser.error(
            "scan Y bounds (%.3f..%.3f) must be within bed depth 0..%.3f"
            % (args.scan_y_min, args.scan_y_max, args.bed_depth)
        )
    if args.feedrate <= 0 or args.travel_feedrate <= 0:
        parser.error("feedrates must be positive")
    if args.dwell_ms < 0:
        parser.error("dwell-ms must be >= 0")
    if args.camera_height <= 0:
        parser.error("camera-height must be positive")


def _fmt(value):
    """Format a coordinate/feedrate rounded to 3 decimals, no trailing zeros."""
    rounded = round(value, 3)
    text = ("%.3f" % rounded).rstrip("0").rstrip(".")
    return text if text else "0"


def generate_gcode(args):
    """Build the gcode lines and return (lines, stats)."""
    x_min, x_max = args.scan_x_min, args.scan_x_max
    y_min, y_max = args.scan_y_min, args.scan_y_max
    spacing = args.line_spacing
    feed = _fmt(args.feedrate)
    travel = _fmt(args.travel_feedrate)

    scan_y_range = y_max - y_min
    row_count = int(math.floor(scan_y_range / spacing)) + 1

    lines = []
    # Stats for the time estimate: total distance per feedrate plus dwells.
    scan_distance = 0.0
    travel_distance = 0.0
    dwell_total_s = 0.0

    # --- Header ---
    lines.append("; Scanning microscope pattern")
    lines.append(
        "; generated by scanner/gcode_generator.py on %s"
        % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    lines.append("; parameters:")
    lines.append(";   output          = %s" % args.output)
    lines.append(";   bed_width       = %s mm" % _fmt(args.bed_width))
    lines.append(";   bed_depth       = %s mm" % _fmt(args.bed_depth))
    lines.append(";   scan_x_min      = %s mm" % _fmt(x_min))
    lines.append(";   scan_x_max      = %s mm" % _fmt(x_max))
    lines.append(";   scan_y_min      = %s mm" % _fmt(y_min))
    lines.append(";   scan_y_max      = %s mm" % _fmt(y_max))
    lines.append(";   line_spacing    = %s mm" % _fmt(spacing))
    if args.overlap is not None:
        lines.append(
            ";   overlap         = %s %% (informational only)"
            % _fmt(args.overlap)
        )
    lines.append(";   feedrate        = %s mm/min" % feed)
    lines.append(";   travel_feedrate = %s mm/min" % travel)
    lines.append(";   dwell_ms        = %d ms" % args.dwell_ms)
    lines.append(";   camera_height   = %s mm" % _fmt(args.camera_height))
    lines.append(";   rows            = %d" % row_count)
    lines.append("")

    # --- Setup ---
    lines.append("G90 ; use absolute coordinates")
    lines.append("G21 ; millimeter units")
    lines.append("G28 ; home all axes")
    lines.append(
        "G1 Z%s F%s ; raise to camera height"
        % (_fmt(args.camera_height), travel)
    )
    lines.append("")

    # --- Move to scan start corner ---
    lines.append("; move to scan start corner")
    lines.append(
        "G1 X%s Y%s F%s" % (_fmt(x_min), _fmt(y_min), travel)
    )
    travel_distance += math.hypot(x_min, y_min)

    # --- Boustrophedon raster ---
    lines.append("")
    lines.append("; boustrophedon raster scan (%d rows)" % row_count)
    for row in range(row_count):
        y = y_min + row * spacing
        if row % 2 == 0:
            # even row: left -> right
            x_target = x_max
        else:
            # odd row: right -> left
            x_target = x_min
        lines.append(
            "G1 X%s Y%s F%s ; row %d"
            % (_fmt(x_target), _fmt(y), feed, row)
        )
        scan_distance += abs(x_max - x_min)
        if args.dwell_ms > 0:
            lines.append("G4 P%d ; let camera settle" % args.dwell_ms)
            dwell_total_s += args.dwell_ms / 1000.0
        # Move up to next row (short Y hop at scan feedrate).
        if row < row_count - 1:
            y_next = y_min + (row + 1) * spacing
            lines.append(
                "G1 X%s Y%s F%s"
                % (_fmt(x_target), _fmt(y_next), feed)
            )
            scan_distance += spacing

    # --- End block ---
    lines.append("")
    lines.append("; end of scan")
    lines.append(
        "G1 Z%s F%s ; lift a bit"
        % (_fmt(args.camera_height + 10), travel)
    )
    lines.append(
        "G1 X%s Y%s F%s ; park near origin"
        % (_fmt(20), _fmt(20), travel)
    )
    travel_distance += math.hypot(
        x_min if (row_count - 1) % 2 == 1 else x_max,
        abs((y_min + (row_count - 1) * spacing) - 20),
    )
    lines.append("; M84 ; uncomment to disable motors")
    lines.append("")

    scan_time_s = scan_distance / (args.feedrate / 60.0)
    travel_time_s = travel_distance / (args.travel_feedrate / 60.0)
    estimated_s = scan_time_s + travel_time_s + dwell_total_s

    stats = {
        "rows": row_count,
        "scan_distance_mm": scan_distance,
        "travel_distance_mm": travel_distance,
        "dwell_total_s": dwell_total_s,
        "estimated_s": estimated_s,
    }
    return lines, stats


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)

    lines, stats = generate_gcode(args)
    with open(args.output, "w") as fh:
        fh.write("\n".join(lines))

    minutes, seconds = divmod(int(round(stats["estimated_s"])), 60)
    print("G-code written to: %s" % args.output)
    print("Rows: %d" % stats["rows"])
    print("Scan distance: %.1f mm, travel distance: %.1f mm"
          % (stats["scan_distance_mm"], stats["travel_distance_mm"]))
    print("Estimated scan time: %dm %02ds (incl. %.1fs dwell)"
          % (minutes, seconds, stats["dwell_total_s"]))


if __name__ == '__main__':
    main()
