# Mesh2 Mapping Generation

This repo uses an offline mesh2 (6-digit) -> municipality code map to resolve PLATEAU tilesets without runtime GIS dependencies.

## 1) Download source data (N03)
- Data: National Land Numerical Information "Administrative Areas (N03)"
- Template page: `https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v3_0.html`

Download the latest N03 dataset from the NLNI download site and keep the file locally.

Helper script:
```bash
python backend/scripts/download_n03_gml.py --year 2025 --output-dir backend/data/n03/2025
```
Use `--include-full` if you want the large nationwide zip (`N03-YYYY0101_GML.zip`).

Extract GeoJSON files from zips:
```bash
python backend/scripts/extract_n03_geojson.py \\
  --input-dir backend/data/n03/2025 \\
  --output-dir backend/data/n03/geojson
```

## 2) Convert to GeoJSON (EPSG:4326)
The generator expects GeoJSON with lon/lat coordinates.

Example using GDAL:
```bash
# Shapefile to GeoJSON
ogr2ogr -f GeoJSON -t_srs EPSG:4326 N03.geojson N03.shp

# GML to GeoJSON (if your download is GML)
ogr2ogr -f GeoJSON -t_srs EPSG:4326 N03.geojson N03.xml
```

## 3) Generate mapping JSON
Run inside the backend conda environment:
```bash
conda run -n paper-cad python backend/scripts/build_mesh2_municipality_map.py \\
  --input N03.geojson \\
  --output backend/data/mesh2_municipality.json
```
You can pass multiple files:
```bash
conda run -n paper-cad python backend/scripts/build_mesh2_municipality_map.py \\
  --input N03_01.geojson N03_02.geojson \\
  --output backend/data/mesh2_municipality.json
```
The generator uses `shapely` (already listed in `backend/environment.yml`).

Optional flags:
- `--min-overlap-ratio 0.01` (exclude tiny overlaps)
- `--code-keys N03_007` (property key for municipality code)

## 4) Runtime configuration
By default the backend reads:
```
backend/data/mesh2_municipality.json
```

Commit the generated JSON to the repo so production deployments can load it without running GIS tooling.

Override with:
```
PLATEAU_MESH2_MAPPING_PATH=/path/to/mesh2_municipality.json
```

If the mapping file is missing, the backend can fall back to a Tokyo-only map:
```
PLATEAU_ALLOW_TOKYO_FALLBACK=true
```
