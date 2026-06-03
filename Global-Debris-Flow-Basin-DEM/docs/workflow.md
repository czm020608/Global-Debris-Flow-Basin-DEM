# Global Debris-Flow Basin DEM Workflow

This project uses a two-CRS rule:

- Source points from Google Maps are stored as WGS84 longitude/latitude: `EPSG:4326`.
- Analysis is done in one local projected metre CRS per basin, usually UTM.

Do not use `EPSG:3857` Web Mercator for basin area, channel length, slope, or station width calculations.

Before running the module commands below, install the repository locally:

```powershell
pip install -e .
```

## 1. Prepare Google Maps point CSV

Recommended input:

```csv
basin_id,point_type,ID,longitude,latitude
JJG,outlet,outlet_01,103.1200,26.2200
JJG,main_start,start_01,103.1779,26.2638
JJG,station,station_01,103.1500,26.2400
```

Allowed `point_type` values:

- `outlet`
- `main_start`
- `station`

The older minimal format `ID,longitude,latitude` is still accepted, but it is treated as one basin with station points only.

## 2. Choose the analysis CRS

Default CRS rule:

- UTM zone: `floor((longitude + 180) / 6) + 1`
- Northern hemisphere: `EPSG:326xx`
- Southern hemisphere: `EPSG:327xx`
- Arctic high latitude: `EPSG:3413`
- Antarctic high latitude: `EPSG:3031`

For the current Jiangjiagou DEM, the analysis CRS is `EPSG:32648`.

## 3. Reproject DEM in QGIS

For each basin:

1. Load the raw DEM.
2. Use `Raster > Projections > Warp (Reproject)`.
3. Set target CRS to the selected local metre CRS.
4. Set output resolution in metres, for example `10`, `12.5`, or `30`.
5. Generate hydrology rasters from the projected DEM:
   - `filled_dem.tif`
   - `flow_dir.tif`
   - `flow_acc.tif`
   - `streams.tif`
   - `watershed.tif`
   - `watershed.shp`

The projected DEM, `flow_dir.tif`, and `flow_acc.tif` must have the same CRS, transform, bounds, and cell size.

## 4. Convert Google points

Use the DEM CRS and sample DEM elevation:

```powershell
python -m debris_flow_dem.functions.prepare_google_points `
  --input point\google_points.csv `
  --dem raster\jiangjiagou.tif `
  --target-crs dem `
  --output-dir point\google_points
```

Or auto-select the CRS from the outlet/first point when no DEM is available:

```powershell
python -m debris_flow_dem.functions.prepare_google_points `
  --input point\google_points.csv `
  --target-crs auto `
  --no-dem `
  --output-dir point\google_points
```

Per-basin outputs:

- `degree_and_radian_points.txt`
- `projected_points.txt`
- `main_channel_start.txt`
- `main_channel_outlet.txt`
- `stations.txt`
- `crs_summary.txt`

`degree_and_radian_points.txt` is only a coordinate record. Use `projected_points.txt` or the split TXT files for QGIS and channel calculations.

## 5. Compute channel and station metrics

Direct command:

```powershell
python -m debris_flow_dem.functions.channel_metrics `
  --dem raster\jiangjiagou.tif `
  --flow-dir temp_working_dir\flow_dir.tif `
  --flow-acc temp_working_dir\flow_acc.tif `
  --watershed temp_working_dir\watershed.tif `
  --start point\google_points\JJG\main_channel_start.txt `
  --outlet point\google_points\JJG\main_channel_outlet.txt `
  --stations point\google_points\JJG\stations.txt `
  --output outputs\JJG\channel_metrics.xlsx `
  --qa-title JJG `
  --start-max-snap-m 100 `
  --outlet-max-snap-m 150 `
  --stream-thresholds 500,1000,2000,5000,10000 `
  --snap-radii-m 25,50,100,200,300
```

Google Maps start/outlet points often do not fall exactly on the DEM-derived
channel. The script therefore tests each `stream threshold x snap distance`
combination, but it handles `main_start` and `outlet` differently.

Start handling uses `--start-max-snap-m`:

- If the input start is within this distance from an extracted stream cell, it
  is snapped and marked as `snapped`.
- If the nearest stream cell is farther away, the candidate is rejected. The
  start point is not relocated automatically, because a far start movement often
  means the upstream channel threshold is too strict, the point/CRS needs review,
  or the DEM-derived channel network missed the small headwater gully.

After the start is accepted, the script traces the DEM-derived main channel
downstream and chooses the point on that traced main channel that is closest to
the input outlet.

Outlet handling uses `--outlet-max-snap-m`:

- If the input outlet is within this distance from the traced main channel, the
  nearest channel point is used and marked as `snapped`.
- If the input outlet is farther away, the nearest point on the traced main
  channel is still adopted as the calculation outlet and marked as `relocated`.
- The old outlet, adopted outlet, and old-to-new distance are written to Excel
  so the difference between the modern map outlet and older DEM channel can be
  reviewed.

Stations are not forced onto the channel; their nearest channel point and
station-channel offset are reported instead.

The script also writes two QA figures by default:

- `QA_Figures/channel_longitudinal_profile.png`: channel elevation profile.
- `QA_Figures/dem_hydrology_qa.png`: DEM background with watershed overlay, traced channel, outlet, start, and station points.

Use `--qa-dir outputs\JJG\QA_Figures` to choose a different figure directory.

One-step point conversion plus metric calculation:

```powershell
python -m debris_flow_dem.pipeline.run_basin_workflow `
  --points point\google_points.csv `
  --dem raster\jiangjiagou.tif `
  --flow-dir temp_working_dir\flow_dir.tif `
  --flow-acc temp_working_dir\flow_acc.tif `
  --watershed temp_working_dir\watershed.tif `
  --output-root outputs\basins `
  --start-max-snap-m 100 `
  --outlet-max-snap-m 150 `
  --stream-thresholds 500,1000,2000,5000,10000 `
  --snap-radii-m 25,50,100,200,300
```

Excel sheets:

- `Summary`: CRS, raster resolution, selected stream threshold, selected snap distance, D8 scheme, start snap distance and threshold, outlet adjustment mode, input/adopted outlet coordinates, input-to-adopted outlet distance, channel length/drop/slope, steepest and gentlest positions, drainage area.
- `Channel_Profile`: per-cell channel profile with distance, coordinates, elevation, segment slope, and flow accumulation.
- `Station_Metrics`: nearest channel position, station-channel offset, manual-review flag, 100 m window slope, and DEM-derived width.
- `Parameter_Search`: all tested `threshold` and `snap_dist` combinations, including failed candidates and the selected-candidate diagnostics.
- QA PNG figures are saved next to the Excel output, and their file paths are recorded in `Summary`.

## 6. Validation checklist

- Load `projected_points.txt` in QGIS with CRS equal to the DEM analysis CRS.
- Confirm start/outlet handling by checking `selected_stream_threshold_cells`, `selected_snap_dist_m`, `start_adjustment`, `start_snap_distance_m`, `start_max_snap_threshold_m`, `outlet_adjustment`, `outlet_input_to_adopted_distance_m`, and `outlet_max_snap_threshold_m`.
- Do not require stations to fall on the channel unless field notes explicitly say so; inspect `station_to_channel_offset_m` and `needs_manual_review`.
- Confirm DEM, `flow_dir.tif`, and `flow_acc.tif` have matching CRS and grid.
- Inspect `traced_end_to_outlet_gap_m` in `Summary`; large values mean the outlet point or snap radius needs review.
- Inspect `needs_manual_review` in `Station_Metrics`; `yes` means the station is farther than the review threshold from the traced channel.
- Treat `dem_cross_section_width_m` as a DEM estimate. Replace or calibrate it with field or image-interpreted widths when available.
