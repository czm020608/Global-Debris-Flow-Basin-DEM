# Data Directory

This directory is intentionally kept lightweight for GitHub.

Recommended layout:

```text
data/
  raw_dem/          Original or projected DEM files.
  google_points/   Google Maps point CSV files and converted point TXT files.
  hydrology/       filled_dem, flow_dir, flow_acc, streams, watershed rasters.
  outputs/         Excel results and QA figures.
```

Large raster files such as `.tif`, `.img`, `.vrt`, and shapefile products are
ignored by `.gitignore` by default. Keep them locally unless you intentionally
publish small example data.

