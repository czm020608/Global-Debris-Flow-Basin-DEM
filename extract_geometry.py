#!/usr/bin/python
# -*- coding: UTF-8 -*-

# __modification time__ = 2026-04-16
# __author__ = Qi Zhou, GFZ Helmholtz Centre for Geosciences
# __find me__ = qi.zhou@gfz.de, qi.zhou.geo@gmail.com, https://github.com/Qi-Zhou-Geo
# Please do not distribute this functions without the author's permission

import numpy as np
import pandas as pd
import argparse

import rasterio
import geopandas as gpd

from whitebox.whitebox_tools import WhiteboxTools

from pathlib import Path

def extracter(file_dir, dem_name, outlet_name,
              threshold=5000, snap_dist=10):

    # (1) define the tool
    wbt = WhiteboxTools()
    wbt.verbose = False # show the prograss bar or not

    # (2) set the working path and file path
    temp_working_dir = Path(f"{file_dir}/temp_working_dir")
    if not temp_working_dir.exists():
        temp_working_dir.mkdir(parents=True)
    wbt.set_working_dir(temp_working_dir)

    dem_file = file_dir / "raster" / dem_name
    outlet_file = file_dir / "point" / outlet_name
    (file_dir / "polyline").mkdir(exist_ok=True)
    (file_dir / "polygon").mkdir(exist_ok=True)

    # (3) check the outlet and dem CRS
    outlet_gpd = gpd.read_file(outlet_file)
    with rasterio.open(dem_file) as src:

        dem_crs = src.crs
        cellsize_x, cellsize_y = src.res
        dem_unit = dem_crs.linear_units

        outlet_crs = outlet_gpd.crs

        if dem_crs == outlet_crs:
            print(f"Both DEM and Outlet with CRS: <{src.crs}>")
        else:
            print(f"DEM CRS: <{dem_crs}>")
            print(f"Outlet CRS: <{outlet_crs}>")
            print(f"Please project the outlet.shp CRS.\n")

    # (4) fill the sink
    wbt.fill_depressions(dem=dem_file, output="filled_dem.tif")
    wbt.d8_pointer(dem="filled_dem.tif", output="flow_dir.tif")
    wbt.d8_flow_accumulation(i="filled_dem.tif", output="flow_acc.tif", out_type="cells")

    # adjust "threshold=1000" based on DEM resolution
    cell_area = cellsize_x * cellsize_y
    drainage_area_m2 = cell_area * threshold
    drainage_area_km2 = drainage_area_m2 / 1e6
    pd.DataFrame(
        [
            {
                "threshold_cells": threshold,
                "snap_dist": snap_dist,
                "cellsize_x": cellsize_x,
                "cellsize_y": cellsize_y,
                "drainage_area_m2": drainage_area_m2,
                "drainage_area_km2": drainage_area_km2,
                "dem_crs": str(dem_crs),
            }
        ]
    ).to_csv(temp_working_dir / "extract_geometry_parameters.csv", index=False)

    print(f"Using threshold = {threshold} for func. <wbt.extract_streams>,\n"
          f"Only areas draining >= {drainage_area_m2:.2f} m² "
          f"({drainage_area_km2:.4f} km²) are classified as streams.\n")

    # (5) extract the streams
    wbt.extract_streams(flow_accum="flow_acc.tif", output="streams.tif", threshold=threshold)
    output_raw_stream = file_dir / "polyline" / "raw_streams.shp"
    wbt.raster_streams_to_vector(streams="streams.tif", d8_pntr="flow_dir.tif",
                                 output=output_raw_stream)
    # set the crs and overwrite it
    streams = gpd.read_file(output_raw_stream)
    streams = streams.set_crs(dem_crs)
    streams.to_file(output_raw_stream, driver="ESRI Shapefile")

   # (6) extract the catchment
    print(f"Using snap_dist = {snap_dist} [{dem_unit}] for <wbt.snap_pour_points>,\n"
          f"meaning the outlet point can be adjusted up to {snap_dist} {dem_unit} "
          f"to align with the nearest stream cell.\n")
    # we need an outlet.shp, we can draw a point in map
    wbt.snap_pour_points(pour_pts=outlet_file, flow_accum="flow_acc.tif",
                         output="snapped_pour_point.shp", snap_dist=snap_dist)

    wbt.watershed(d8_pntr="flow_dir.tif", pour_pts="snapped_pour_point.shp", output="watershed.tif")
    output_watershed = file_dir / "polygon" / "watershed.shp"
    wbt.raster_to_vector_polygons(i="watershed.tif", output=output_watershed)

    # set the crs and overwrite it
    watershed = gpd.read_file(output_watershed)
    watershed = watershed.set_crs(dem_crs)
    watershed.to_file(output_watershed, driver="ESRI Shapefile")


def main():
    parser = argparse.ArgumentParser(description="Create hydrology rasters, stream vector, and watershed polygon.")
    parser.add_argument("--file-dir", default=Path(r"F:\JJG_catchment"), type=Path)
    parser.add_argument("--dem-name", default="jiangjiagou.tif")
    parser.add_argument("--outlet-name", default="outlet.shp")
    parser.add_argument("--threshold", default=5000, type=float)
    parser.add_argument("--snap-dist", default=10, type=float)
    args = parser.parse_args()
    extracter(args.file_dir, args.dem_name, args.outlet_name, args.threshold, args.snap_dist)


if __name__ == "__main__":
    main()
