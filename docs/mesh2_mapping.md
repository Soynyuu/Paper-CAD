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

## How the JSON is generated
The generator reads N03 GeoJSON features and produces a mesh2 (6-digit) to municipality code map:

1) Read features (EPSG:4326 lon/lat).
2) Extract municipality code from `N03_007` (5 digits).
   - Prefecture-level codes ending with `000` are skipped.
3) Merge geometries per municipality (unary union).
4) For each municipality, enumerate mesh2 cells that intersect its bounding box.
5) Test each mesh2 cell for intersection with the municipality polygon.
   - Optional filter: `--min-overlap-ratio` (default: 0.0).
6) Store `mesh2 -> [municipality_code...]` with de-duplicated, sorted codes.

Mesh2 cell size:
- Latitude step: 5/60 degrees
- Longitude step: 7.5/60 degrees

Output format:
```json
{
  "meta": {
    "generated_at": "2025-01-11T10:00:00+00:00",
    "source_name": "National Land Numerical Information (N03 Administrative Areas)",
    "source_url": "https://nlftp.mlit.go.jp/ksj/",
    "input_file": ["N03_01.geojson", "N03_02.geojson"],
    "min_overlap_ratio": 0.0
  },
  "mesh2_to_municipalities": {
    "533945": ["13101", "13102"],
    "533946": ["13101", "13113"]
  }
}
```

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
