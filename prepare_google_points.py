#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prepare Google Maps point coordinates for global debris-flow basin workflows.

Input CSV columns:
    ID, longitude, latitude

Recommended global-basin columns:
    basin_id, point_type, ID, longitude, latitude

point_type values:
    outlet, main_start, station

Outputs are written per basin:
    degree_and_radian_points.txt
    projected_points.txt
    main_channel_start.txt
    main_channel_outlet.txt
    stations.txt
    crs_summary.txt
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd
import rasterio
from pyproj import CRS, Transformer


WGS84_CRS = "EPSG:4326"
POINT_TYPES = {"outlet", "main_start", "station"}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "id": "ID",
        "name": "ID",
        "station_id": "ID",
        "basin": "basin_id",
        "basinid": "basin_id",
        "basin_id": "basin_id",
        "pointtype": "point_type",
        "point_type": "point_type",
        "type": "point_type",
        "lon": "longitude",
        "lng": "longitude",
        "x": "longitude",
        "\u7ecf\u5ea6": "longitude",
        "lat": "latitude",
        "y": "latitude",
        "\u7eac\u5ea6": "latitude",
    }
    renamed = {}
    for col in df.columns:
        key = str(col).strip().lower()
        renamed[col] = aliases.get(key, str(col).strip())
    df = df.rename(columns=renamed)

    required = {"ID", "longitude", "latitude"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(sorted(missing))}")

    out = df.copy()
    if "basin_id" not in out.columns:
        out["basin_id"] = "basin_001"
    if "point_type" not in out.columns:
        out["point_type"] = "station"

    out["ID"] = out["ID"].astype(str)
    out["basin_id"] = out["basin_id"].astype(str)
    out["point_type"] = out["point_type"].astype(str).str.strip().str.lower()
    out["longitude"] = pd.to_numeric(out["longitude"])
    out["latitude"] = pd.to_numeric(out["latitude"])

    invalid_types = sorted(set(out["point_type"]).difference(POINT_TYPES))
    if invalid_types:
        raise ValueError(
            "Invalid point_type value(s): "
            + ", ".join(invalid_types)
            + ". Use outlet, main_start or station."
        )
    if not out["longitude"].between(-180, 180).all():
        raise ValueError("Longitude values must be in [-180, 180] degrees.")
    if not out["latitude"].between(-90, 90).all():
        raise ValueError("Latitude values must be in [-90, 90] degrees.")

    return out


def choose_analysis_crs(longitude: float, latitude: float) -> CRS:
    """Choose a meter-based projected CRS for one basin."""
    if latitude >= 84:
        return CRS.from_epsg(3413)
    if latitude <= -80:
        return CRS.from_epsg(3031)

    zone = int(math.floor((longitude + 180) / 6) + 1)
    zone = min(max(zone, 1), 60)
    epsg = 32600 + zone if latitude >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def _basin_reference_lonlat(df: pd.DataFrame) -> tuple[float, float]:
    outlets = df[df["point_type"] == "outlet"]
    ref = outlets.iloc[0] if not outlets.empty else df.iloc[0]
    return float(ref["longitude"]), float(ref["latitude"])


def _resolve_target_crs(target_crs: str, dem_path: Path | None, basin_df: pd.DataFrame) -> CRS:
    target = target_crs.strip().lower()
    if target == "dem":
        if dem_path is None:
            raise ValueError("--dem is required when --target-crs dem is used.")
        with rasterio.open(dem_path) as dem:
            if dem.crs is None:
                raise ValueError(f"DEM has no CRS: {dem_path}")
            crs = CRS.from_user_input(dem.crs)
    elif target == "auto":
        lon, lat = _basin_reference_lonlat(basin_df)
        crs = choose_analysis_crs(lon, lat)
    else:
        crs = CRS.from_user_input(target_crs)

    epsg = crs.to_epsg()
    if epsg == 3857:
        raise ValueError("EPSG:3857 Web Mercator is not allowed for length/area/slope analysis.")
    if not crs.is_projected:
        raise ValueError(f"Target CRS must be projected and meter-based, got: {crs.to_string()}")
    return crs


def _sample_dem_z(dem_path: Path, xs: list[float], ys: list[float]) -> list[float | None]:
    with rasterio.open(dem_path) as dem:
        nodata = dem.nodata
        bounds = dem.bounds
        values = []
        for x, y, value in zip(xs, ys, dem.sample(zip(xs, ys))):
            if x < bounds.left or x > bounds.right or y < bounds.bottom or y > bounds.top:
                values.append(None)
                continue
            z = float(value[0])
            if nodata is not None and z == nodata:
                values.append(None)
            else:
                values.append(z)
    return values


def _validate_dem_crs(dem_path: Path, target_crs: CRS) -> None:
    with rasterio.open(dem_path) as dem:
        if dem.crs is None:
            raise ValueError(f"DEM has no CRS: {dem_path}")
        dem_crs = CRS.from_user_input(dem.crs)
    if dem_crs != target_crs:
        raise ValueError(
            f"DEM CRS ({dem_crs.to_string()}) does not match target analysis CRS "
            f"({target_crs.to_string()}). Reproject the DEM first or use --target-crs dem."
        )


def _write_point_subset(df: pd.DataFrame, path: Path, point_type: str) -> None:
    subset = df[df["point_type"] == point_type]
    subset[["ID", "X", "Y", "Z"]].to_csv(path, index=False, sep="\t", float_format="%.3f")


def prepare_points(
    input_csv: Path,
    dem_path: Path | None,
    output_dir: Path,
    target_crs: str = "dem",
) -> list[dict[str, str]]:
    df = _normalise_columns(pd.read_csv(input_csv))
    output_dir.mkdir(parents=True, exist_ok=True)

    df["longitude_rad"] = df["longitude"].map(math.radians)
    df["latitude_rad"] = df["latitude"].map(math.radians)

    manifests = []
    for basin_id, basin_df in df.groupby("basin_id", sort=True):
        basin_dir = output_dir / str(basin_id)
        basin_dir.mkdir(parents=True, exist_ok=True)
        basin_df = basin_df.copy()
        crs = _resolve_target_crs(target_crs, dem_path, basin_df)
        if dem_path:
            _validate_dem_crs(dem_path, crs)

        transformer = Transformer.from_crs(WGS84_CRS, crs, always_xy=True)
        projected = [
            transformer.transform(lon, lat)
            for lon, lat in zip(basin_df["longitude"], basin_df["latitude"])
        ]
        basin_df["X"] = [xy[0] for xy in projected]
        basin_df["Y"] = [xy[1] for xy in projected]
        basin_df["Z"] = _sample_dem_z(dem_path, basin_df["X"].tolist(), basin_df["Y"].tolist()) if dem_path else None

        radian_cols = [
            "basin_id",
            "point_type",
            "ID",
            "longitude",
            "latitude",
            "longitude_rad",
            "latitude_rad",
        ]
        extra_cols = [c for c in basin_df.columns if c not in set(radian_cols + ["X", "Y", "Z"])]
        radian_path = basin_dir / "degree_and_radian_points.txt"
        basin_df[radian_cols + extra_cols].to_csv(radian_path, index=False, sep="\t", float_format="%.12f")

        projected_path = basin_dir / "projected_points.txt"
        projected_cols = ["basin_id", "point_type", "ID", "X", "Y", "Z"] + extra_cols
        basin_df[projected_cols].to_csv(projected_path, index=False, sep="\t", float_format="%.3f")

        start_path = basin_dir / "main_channel_start.txt"
        outlet_path = basin_dir / "main_channel_outlet.txt"
        stations_path = basin_dir / "stations.txt"
        _write_point_subset(basin_df, start_path, "main_start")
        _write_point_subset(basin_df, outlet_path, "outlet")
        _write_point_subset(basin_df, stations_path, "station")

        manifest_path = basin_dir / "crs_summary.txt"
        epsg = crs.to_epsg()
        manifest_path.write_text(
            "\n".join(
                [
                    f"basin_id\t{basin_id}",
                    "source_crs\tEPSG:4326",
                    f"analysis_crs\t{crs.to_string()}",
                    f"analysis_epsg\t{epsg if epsg is not None else ''}",
                    f"target_crs_mode\t{target_crs}",
                    "x_y_units\tmetre",
                    "z_source\tDEM sample" if dem_path else "z_source\tnot sampled",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        manifests.append(
            {
                "basin_id": str(basin_id),
                "analysis_crs": crs.to_string(),
                "radian_path": str(radian_path),
                "projected_path": str(projected_path),
                "start_path": str(start_path),
                "outlet_path": str(outlet_path),
                "stations_path": str(stations_path),
                "manifest_path": str(manifest_path),
            }
        )

    pd.DataFrame(manifests).to_csv(output_dir / "basin_point_outputs.csv", index=False)
    return manifests


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Google Maps lon/lat points to DEM-analysis TXT files.")
    parser.add_argument("--input", required=True, type=Path, help="CSV with basin_id, point_type, ID, longitude, latitude.")
    parser.add_argument("--dem", default=Path("raster/jiangjiagou.tif"), type=Path, help="DEM raster for CRS/Z sampling.")
    parser.add_argument("--output-dir", default=Path("point/google_points"), type=Path, help="Output folder for TXT files.")
    parser.add_argument(
        "--target-crs",
        default="dem",
        help="Target projected CRS: dem, auto, or an explicit CRS such as EPSG:32648.",
    )
    parser.add_argument("--no-dem", action="store_true", help="Do not read a DEM; requires --target-crs auto or explicit CRS.")
    args = parser.parse_args()

    dem_path = None if args.no_dem else args.dem
    manifests = prepare_points(args.input, dem_path, args.output_dir, args.target_crs)
    for item in manifests:
        print(f"{item['basin_id']}: {item['analysis_crs']}")
        print(f"Wrote {item['projected_path']}")


if __name__ == "__main__":
    main()
