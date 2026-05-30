#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Run the point-preparation and channel-metrics workflow for one or more basins.

This script assumes QGIS/Whitebox hydrology rasters already exist for each
target basin. It does not reproject DEMs or create flow_dir/flow_acc rasters;
those remain QGIS/Whitebox preprocessing steps.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from channel_metrics import compute_metrics, parse_float_list
from prepare_google_points import prepare_points


def _existing_or_none(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run global debris-flow basin point and channel metric workflow.")
    parser.add_argument("--points", required=True, type=Path, help="Google Maps CSV with basin_id, point_type, ID, lon, lat.")
    parser.add_argument("--dem", required=True, type=Path, help="Projected DEM in the basin analysis CRS.")
    parser.add_argument("--flow-dir", required=True, type=Path, help="D8 flow direction raster aligned with DEM.")
    parser.add_argument("--flow-acc", required=True, type=Path, help="Flow accumulation raster aligned with DEM.")
    parser.add_argument("--output-root", default=Path("outputs/basins"), type=Path)
    parser.add_argument("--target-crs", default="dem", help="dem, auto, or explicit projected CRS such as EPSG:32648.")
    parser.add_argument("--snap-radius-m", default=100.0, type=float)
    parser.add_argument(
        "--stream-thresholds",
        default="500,1000,2000,5000,10000",
        help="Comma-separated flow_acc thresholds in cells to test for channel snapping.",
    )
    parser.add_argument(
        "--snap-radii-m",
        default="25,50,100,200,300",
        help="Comma-separated snap distances in metres to test for start/outlet snapping.",
    )
    parser.add_argument("--pointer-scheme", choices=["auto", "whitebox", "esri"], default="auto")
    parser.add_argument("--slope-window-m", default=100.0, type=float)
    parser.add_argument("--bank-relief-m", default=5.0, type=float)
    parser.add_argument("--max-width-m", default=300.0, type=float)
    parser.add_argument("--station-offset-review-m", default=100.0, type=float)
    args = parser.parse_args()

    points_root = args.output_root / "points"
    metrics_root = args.output_root / "metrics"
    manifests = prepare_points(args.points, args.dem, points_root, args.target_crs)

    for manifest in manifests:
        basin_id = manifest["basin_id"]
        basin_points = points_root / basin_id
        start_path = basin_points / "main_channel_start.txt"
        outlet_path = basin_points / "main_channel_outlet.txt"
        stations_path = _existing_or_none(basin_points / "stations.txt")
        output_path = metrics_root / basin_id / "channel_metrics.xlsx"

        compute_metrics(
            args.dem,
            args.flow_dir,
            args.flow_acc,
            start_path,
            outlet_path,
            stations_path,
            output_path,
            args.snap_radius_m,
            args.pointer_scheme,
            args.slope_window_m,
            args.bank_relief_m,
            args.max_width_m,
            args.station_offset_review_m,
            parse_float_list(args.stream_thresholds, [500.0, 1000.0, 2000.0, 5000.0, 10000.0]),
            parse_float_list(args.snap_radii_m, [args.snap_radius_m]),
        )
        print(f"{basin_id}: wrote {output_path}")


if __name__ == "__main__":
    main()
