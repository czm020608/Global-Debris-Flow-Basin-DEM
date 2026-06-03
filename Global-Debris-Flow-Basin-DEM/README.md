# Global Debris-Flow Basin DEM

This repository organizes a DEM-based workflow for debris-flow basin analysis.
The workflow converts Google Maps points, chooses a local projected analysis CRS,
processes DEM hydrology rasters, extracts the main channel, checks start/outlet
point reliability, calculates channel and station metrics, and writes Excel plus
QA figures.

## Repository Structure

```text
Global-Debris-Flow-Basin-DEM/
  data/
    raw_dem/          DEM files, kept locally by default.
    google_points/   Google Maps point CSV and converted point files.
    hydrology/       filled_dem, flow_dir, flow_acc, streams, watershed.
    outputs/         Excel results and QA figures.
  src/
    debris_flow_dem/
      functions/     Reusable processing modules.
      pipeline/      One-step workflow scripts.
  docs/
    workflow.md      Detailed processing manual.
  examples/
    google_points_template.csv
```

## Main Files

- `src/debris_flow_dem/functions/prepare_google_points.py`
  converts Google Maps longitude/latitude points to projected TXT files and
  samples DEM elevation.
- `src/debris_flow_dem/functions/channel_metrics.py`
  calculates main-channel metrics, station metrics, outlet relocation, start
  snap checking, Excel output, and QA figures.
- `src/debris_flow_dem/functions/extract_geometry.py`
  extracts watershed and stream geometry using hydrology preprocessing outputs.
- `src/debris_flow_dem/pipeline/run_basin_workflow.py`
  runs point conversion and metric calculation in one command.

## Point Rule

Google Maps points are stored in `EPSG:4326`. Analysis uses a local metre CRS,
usually UTM. Do not use `EPSG:3857` for area, length, or slope calculation.

The start and outlet points are treated differently:

- Start point: only near-channel snapping is allowed. If it is farther than
  `--start-max-snap-m`, the candidate is rejected and should be reviewed.
- Outlet point: if near the DEM-derived main channel it is snapped; if far away,
  the nearest point on the traced DEM channel is adopted and marked as relocated.

## Example

Install the package locally first:

```powershell
pip install -e .
```

```powershell
python -m debris_flow_dem.pipeline.run_basin_workflow `
  --points data\google_points\google_points.csv `
  --dem data\raw_dem\basin_dem.tif `
  --flow-dir data\hydrology\flow_dir.tif `
  --flow-acc data\hydrology\flow_acc.tif `
  --watershed data\hydrology\watershed.tif `
  --output-root data\outputs `
  --start-max-snap-m 100 `
  --outlet-max-snap-m 150 `
  --stream-thresholds 100,300,500,1000,2000,5000 `
  --snap-radii-m 25,50,100,200,300
```

See `docs/workflow.md` for the full workflow and validation checklist.
