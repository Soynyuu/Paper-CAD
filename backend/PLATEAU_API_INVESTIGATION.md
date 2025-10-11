# PLATEAU API Investigation Report

## Summary

The PLATEAU Data Catalog API that was expected to provide CityGML data by coordinates **does not exist or is no longer available**. The API endpoint we attempted to use returns 404 errors for all locations.

## Test Results

Tested endpoint: `https://api.plateauview.mlit.go.jp/datacatalog/citygml/r:{lon1},{lat1},{lon2},{lat2}`

**All locations returned 404:**
- Tokyo Station: 404
- Shibuya Scramble Square: 404
- Toyosu: 404
- Marunouchi: 404

Response: `{"error":"not found"}`

## What Exists

### 1. PLATEAU Data Catalog API
- **URL**: `https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets`
- **Format**: JSON
- **Content**: List of 3D Tiles datasets (NOT CityGML)
- **Data**: Organized by prefecture/city/ward
- **Use case**: Streaming 3D Tiles for visualization

### 2. G空間情報センター (G-Spatial Information Center)
- **URL**: https://www.geospatial.jp/ckan/dataset/plateau
- **Format**: Manual download portal
- **Content**: Original CityGML files (v2 and v3)
- **Organization**: By region (e.g., Tokyo 23-ku)
- **File size**: Very large (5GB+ for Tokyo 23-ku)
- **API**: CKAN-based, but access restrictions or errors observed

### 3. PLATEAU Open Data Portal
- **URL**: https://www.mlit.go.jp/plateau/open-data/
- **Access**: Manual download through web interface
- **Process**: Select region → Click CityGML version → Download ZIP

## Why Our Implementation Fails

The geocoding component works correctly:
- ✅ Nominatim API returns correct coordinates
- ✅ Multi-candidate selection with relevance scoring
- ✅ Japan coordinate validation

However, the PLATEAU CityGML fetch step fails:
- ❌ No live API for fetching CityGML by coordinates
- ❌ Original endpoint no longer exists or was never publicly available

## Alternative Approaches

### Option 1: Use 3D Tiles Instead of CityGML
**Pros:**
- Live API available
- Organized by city/ward
- Smaller file sizes

**Cons:**
- Major architecture change required
- Different data format (not CityGML)
- Would need new parser and converter

**Implementation:**
1. Geocode address → Get coordinates
2. Determine city/ward from coordinates
3. Fetch 3D Tiles dataset from Data Catalog API
4. Parse 3D Tiles → Extract building geometry
5. Convert to STEP

### Option 2: Pre-download Regional CityGML Files
**Pros:**
- Use existing CityGML pipeline
- High-quality PLATEAU data
- Fast local queries

**Cons:**
- Large storage requirement (5GB+ per region)
- Manual setup required
- Need to maintain data updates

**Implementation:**
1. Pre-download CityGML for target regions (Tokyo, Osaka, etc.)
2. Index buildings by coordinates
3. Geocode address → Query local index
4. Extract relevant buildings from local CityGML
5. Use existing converter

### Option 3: Use OpenStreetMap Building Data
**Pros:**
- Live API available (Overpass API)
- Global coverage
- Free and open

**Cons:**
- Lower quality than PLATEAU
- Less detailed building models
- No height information in many cases

**Implementation:**
1. Geocode address → Get coordinates
2. Query Overpass API for buildings in radius
3. Extract OSM building footprints
4. Extrude to simple 3D shapes
5. Convert to STEP

### Option 4: Hybrid Approach
**Pros:**
- Best of both worlds
- Graceful degradation

**Cons:**
- More complex
- Multiple data sources to maintain

**Implementation:**
1. Geocode address → Get coordinates
2. Try local PLATEAU CityGML cache (if available)
3. If not found, fall back to OSM building data
4. Convert to STEP

## Recommendation

Given the constraints, I recommend **Option 2 (Pre-download Regional CityGML)** for the following reasons:

1. **Works with existing codebase**: No need to rewrite the CityGML parser
2. **High quality**: Uses official PLATEAU data
3. **Good performance**: Local queries are fast
4. **Focused scope**: Tokyo region covers most user needs

### Implementation Plan

1. **Download CityGML for Tokyo 23-ku** (~5GB)
   - Store in `backend/data/plateau/tokyo23ku/`
   - Parse and index on startup

2. **Create building index**
   - Extract all building IDs and coordinates
   - Store in SQLite or JSON for fast lookup
   - Format: `{ "building_id": "...", "lat": 35.xxx, "lon": 139.xxx, "file": "udx/bldg/..." }`

3. **Modify plateau_fetcher.py**
   - Instead of fetching from API, query local index
   - Find buildings within radius
   - Extract relevant CityGML fragments
   - Pass to existing converter

4. **Add management commands**
   - `python manage_plateau.py download tokyo23ku`
   - `python manage_plateau.py index`
   - `python manage_plateau.py update`

## Next Steps

1. **Confirm approach with user**
   - Which option to pursue?
   - Target regions (Tokyo? Other cities?)
   - Storage constraints?

2. **If Option 2 (Pre-download):**
   - Download Tokyo 23-ku CityGML
   - Build indexing system
   - Modify fetcher to use local data

3. **If Option 1 (3D Tiles):**
   - Research 3D Tiles format
   - Build 3D Tiles parser
   - Modify converter pipeline

4. **If Option 3 (OSM):**
   - Integrate Overpass API
   - Build OSM → CityGML converter
   - Handle lower data quality

## References

- PLATEAU Open Data: https://www.mlit.go.jp/plateau/open-data/
- Data Catalog API: https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets
- G-Spatial Information Center: https://www.geospatial.jp/ckan/dataset/plateau
- PLATEAU Streaming Tutorial: https://github.com/Project-PLATEAU/plateau-streaming-tutorial
