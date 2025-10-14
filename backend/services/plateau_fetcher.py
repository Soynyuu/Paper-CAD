"""
PLATEAU Building Fetcher Service

This module provides functionality to automatically fetch PLATEAU CityGML data
by geocoding addresses or facility names and retrieving nearby buildings from
the PLATEAU Data Catalog API.

Key Features:
- Geocode addresses/facility names to coordinates (OpenStreetMap Nominatim)
- Fetch CityGML data from PLATEAU Data Catalog API
- Parse building information from CityGML XML
- Find nearest buildings to target coordinates

API Rate Limits:
- Nominatim: 1 request per second (strictly enforced)
- PLATEAU Data Catalog: No known limits (use reasonable requests)

Usage:
    from services.plateau_fetcher import search_buildings_by_address

    result = search_buildings_by_address("東京駅", radius=0.001, limit=10)
    if result["success"]:
        buildings = result["buildings"]
        nearest = buildings[0]  # Sorted by distance
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import requests
from shapely.geometry import Point
from shapely import distance

# Import mesh code utilities
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from mesh_utils import latlon_to_mesh_3rd, get_neighboring_meshes_3rd


# CityGML namespaces (same as citygml_to_step.py)
NS = {
    "gml": "http://www.opengis.net/gml",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "core": "http://www.opengis.net/citygml/2.0",
    "uro": "http://www.opengis.net/uro/1.0",
    "gen": "http://www.opengis.net/citygml/generics/2.0",
    "xlink": "http://www.w3.org/1999/xlink",
}


@dataclass
class BuildingInfo:
    """Information about a PLATEAU building.

    Attributes:
        building_id: Stable building ID (e.g., "13101-bldg-123456")
        gml_id: Technical GML identifier (e.g., "BLD_uuid")
        latitude: Latitude in WGS84
        longitude: Longitude in WGS84
        distance_meters: Distance from search point in meters
        height: Building height in meters (optional)
        usage: Building usage type (optional)
        measured_height: Measured height attribute (optional)
        name: Building name from CityGML (optional)
    """
    building_id: Optional[str]
    gml_id: str
    latitude: float
    longitude: float
    distance_meters: float
    height: Optional[float] = None
    usage: Optional[str] = None
    measured_height: Optional[float] = None
    name: Optional[str] = None


@dataclass
class GeocodingResult:
    """Result from geocoding an address/facility name.

    Attributes:
        query: Original search query
        latitude: Geocoded latitude
        longitude: Geocoded longitude
        display_name: Human-readable address
        osm_type: OSM object type (node, way, relation)
        osm_id: OSM object ID
    """
    query: str
    latitude: float
    longitude: float
    display_name: str
    osm_type: Optional[str] = None
    osm_id: Optional[int] = None


def geocode_address(
    query: str,
    country_codes: str = "jp",
    timeout: int = 10
) -> Optional[GeocodingResult]:
    """Geocode an address or facility name to coordinates using Nominatim.

    Args:
        query: Address or facility name (e.g., "東京駅", "東京都千代田区丸の内1-9-1")
        country_codes: Country code filter (default: "jp" for Japan)
        timeout: Request timeout in seconds

    Returns:
        GeocodingResult if successful, None otherwise

    Rate Limit:
        MUST respect Nominatim's 1 request/second limit.
        This function includes time.sleep(1) to enforce the limit.

    Strategy:
        Tries multiple search strategies with fallback:
        1. Original query with multiple results
        2. Validates Japan coordinates (lat: 20-50, lon: 120-155)
        3. Prefers building/amenity types over generic results

    Example:
        >>> result = geocode_address("東京駅")
        >>> if result:
        ...     print(f"Found: {result.display_name}")
        ...     print(f"Coordinates: ({result.latitude}, {result.longitude})")
    """
    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"

    # Request parameters - get multiple results for better selection
    params = {
        "q": query,
        "format": "json",
        "limit": 5,  # Get multiple candidates
        "countrycodes": country_codes,
        "addressdetails": 1,
    }

    # User-Agent is required by Nominatim usage policy
    headers = {
        "User-Agent": "Paper-CAD/1.0 (https://github.com/Soynyuu/paper-cad)"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()

        data = response.json()

        if not data or len(data) == 0:
            print(f"[GEOCODING] No results found for query: {query}")
            print(f"[GEOCODING] Suggestion: Try using a landmark or area name instead of detailed address")
            return None

        print(f"[GEOCODING] Found {len(data)} candidate(s) for: {query}")

        # Filter and rank results
        valid_results = []
        for i, result in enumerate(data):
            try:
                lat = float(result["lat"])
                lon = float(result["lon"])

                # Validate Japan coordinates
                if not (20 <= lat <= 50 and 120 <= lon <= 155):
                    print(f"[GEOCODING]   Candidate {i+1}: Outside Japan, skipping")
                    continue

                # Calculate relevance score
                score = _calculate_relevance_score(result, query)

                valid_results.append({
                    "result": result,
                    "lat": lat,
                    "lon": lon,
                    "score": score
                })

                print(f"[GEOCODING]   Candidate {i+1}: {result.get('display_name', 'N/A')[:80]}")
                print(f"[GEOCODING]     Type: {result.get('class', 'N/A')}/{result.get('type', 'N/A')}, Score: {score:.2f}")

            except (KeyError, ValueError) as e:
                print(f"[GEOCODING]   Candidate {i+1}: Parse error, skipping")
                continue

        if not valid_results:
            print(f"[GEOCODING] No valid results in Japan for query: {query}")
            return None

        # Sort by score and select best match
        valid_results.sort(key=lambda x: x["score"], reverse=True)
        best = valid_results[0]
        result = best["result"]

        geocoding_result = GeocodingResult(
            query=query,
            latitude=best["lat"],
            longitude=best["lon"],
            display_name=result.get("display_name", ""),
            osm_type=result.get("osm_type"),
            osm_id=result.get("osm_id")
        )

        print(f"[GEOCODING] ✓ Selected best match (score: {best['score']:.2f})")
        print(f"[GEOCODING]   Coordinates: ({geocoding_result.latitude}, {geocoding_result.longitude})")
        print(f"[GEOCODING]   Address: {geocoding_result.display_name}")

        return geocoding_result

    except requests.exceptions.RequestException as e:
        print(f"[GEOCODING] Request failed: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"[GEOCODING] Parse error: {e}")
        return None
    finally:
        # CRITICAL: Enforce Nominatim rate limit (1 req/sec)
        time.sleep(1)


def _calculate_relevance_score(result: dict, query: str) -> float:
    """Calculate relevance score for a geocoding result.

    Higher score = more relevant result

    Scoring factors:
    - Building/amenity: +10 points
    - Station/railway: +8 points
    - Place/locality: +5 points
    - Query substring match: +15 points
    - Importance value: +0 to +10 points
    """
    score = 0.0

    # Type-based scoring
    result_class = result.get("class", "")
    result_type = result.get("type", "")

    if result_class == "building" or result_type == "building":
        score += 10
    elif result_class == "amenity":
        score += 10
    elif result_class == "railway" or result_type == "station":
        score += 8
    elif result_class == "place":
        score += 5

    # Name matching
    display_name = result.get("display_name", "").lower()
    query_lower = query.lower()

    # Exact match in display name
    if query_lower in display_name:
        score += 15

    # OSM importance (0.0 to 1.0)
    importance = result.get("importance", 0.0)
    score += importance * 10

    return score


def fetch_citygml_from_plateau(
    latitude: float,
    longitude: float,
    radius: float = 0.001,
    timeout: int = 30
) -> Optional[str]:
    """Fetch CityGML data from PLATEAU Data Catalog API using mesh codes.

    Args:
        latitude: Center latitude (WGS84)
        longitude: Center longitude (WGS84)
        radius: Search radius (currently ignored, uses 3rd mesh + neighbors)
        timeout: Request timeout in seconds

    Returns:
        Combined CityGML XML content as string if successful, None otherwise

    Strategy:
        1. Calculate 3rd mesh code (1km) for coordinates
        2. Get neighboring mesh codes (3x3 grid = 9 meshes total)
        3. Query PLATEAU API with mesh codes to get CityGML file URLs
        4. Download building CityGML files
        5. Combine into single XML document

    Example:
        >>> xml = fetch_citygml_from_plateau(35.681236, 139.767125)
        >>> if xml:
        ...     print(f"Fetched {len(xml)} bytes of CityGML data")
    """
    print(f"[PLATEAU] Fetching CityGML for ({latitude}, {longitude})")

    # Step 1: Calculate mesh code for center point
    # Note: Using only center mesh (1km x 1km) to avoid downloading too many files
    #       If radius > ~500m is needed, consider adding neighbors
    try:
        center_mesh = latlon_to_mesh_3rd(latitude, longitude)
        print(f"[PLATEAU] Center mesh: {center_mesh} (1km x 1km area)")
    except Exception as e:
        print(f"[PLATEAU] Failed to calculate mesh code: {e}")
        return None

    # Step 2: Query PLATEAU API with mesh code
    api_url = f"https://api.plateauview.mlit.go.jp/datacatalog/citygml/m:{center_mesh}"

    print(f"[PLATEAU] Querying API...")

    try:
        response = requests.get(api_url, timeout=timeout)
        response.raise_for_status()
        catalog_data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"[PLATEAU] API request failed: {e}")
        return None
    except ValueError as e:
        print(f"[PLATEAU] Invalid JSON response: {e}")
        return None

    # Step 3: Extract building CityGML file URLs
    citygml_urls = []
    MAX_FILES = 5  # Limit to prevent memory issues

    if "cities" in catalog_data:
        for city in catalog_data["cities"]:
            city_name = city.get("cityName", "Unknown")
            files = city.get("files", {})
            bldg_files = files.get("bldg", [])

            print(f"[PLATEAU] {city_name}: {len(bldg_files)} building file(s)")

            for bldg_file in bldg_files:
                url = bldg_file.get("url")
                if url:
                    citygml_urls.append(url)
                    if len(citygml_urls) >= MAX_FILES:
                        break

            if len(citygml_urls) >= MAX_FILES:
                break

    if not citygml_urls:
        print(f"[PLATEAU] No CityGML files found in response")
        return None

    if len(citygml_urls) > MAX_FILES:
        citygml_urls = citygml_urls[:MAX_FILES]
        print(f"[PLATEAU] Limited to {MAX_FILES} file(s) to prevent memory issues")

    print(f"[PLATEAU] Downloading {len(citygml_urls)} CityGML file(s)...")

    # Step 4: Download and combine CityGML files
    combined_xml = _download_and_combine_citygml(citygml_urls, timeout=timeout)

    if combined_xml:
        print(f"[PLATEAU] Success: Combined {len(combined_xml)} bytes from {len(citygml_urls)} file(s)")
    else:
        print(f"[PLATEAU] Failed to download CityGML files")

    return combined_xml


def _download_and_combine_citygml(urls: List[str], timeout: int = 30) -> Optional[str]:
    """Download multiple CityGML files and combine into single XML document.

    Args:
        urls: List of CityGML file URLs
        timeout: Request timeout in seconds

    Returns:
        Combined CityGML XML as string, or None if failed
    """
    # Download first file as base
    if not urls:
        return None

    print(f"[PLATEAU] Downloading {len(urls)} file(s)...")

    try:
        # Download first file as base document
        response = requests.get(urls[0], timeout=timeout)
        response.raise_for_status()
        base_xml = response.text

        # Parse base XML
        try:
            root = ET.fromstring(base_xml)
        except ET.ParseError as e:
            print(f"[PLATEAU] Failed to parse base XML: {e}")
            return None

        # If only one file, return it
        if len(urls) == 1:
            return base_xml

        # Download and merge remaining files
        for i, url in enumerate(urls[1:], 2):
            try:
                print(f"[PLATEAU]   Downloading file {i}/{len(urls)}...")
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()

                # Parse additional XML
                additional_root = ET.fromstring(response.text)

                # Find all cityObjectMember elements and append to base
                for member in additional_root.findall(".//{http://www.opengis.net/citygml/2.0}cityObjectMember"):
                    root.append(member)

            except Exception as e:
                print(f"[PLATEAU]   Warning: Failed to download file {i}: {e}")
                continue

        # Convert back to string
        combined_xml = ET.tostring(root, encoding="unicode")
        return combined_xml

    except requests.exceptions.RequestException as e:
        print(f"[PLATEAU] Download failed: {e}")
        return None
    except Exception as e:
        print(f"[PLATEAU] Unexpected error: {e}")
        return None


def parse_buildings_from_citygml(
    xml_content: str
) -> List[BuildingInfo]:
    """Parse building information from CityGML XML.

    Extracts:
    - Building ID (generic attribute "建物ID" or "buildingID")
    - gml:id (fallback identifier)
    - Coordinates (from footprint or first posList)
    - Height (from measuredHeight or buildingHeight)
    - Usage (from bldg:usage)
    - Building name (from gml:name or uro:buildingName)

    Args:
        xml_content: CityGML XML as string

    Returns:
        List of BuildingInfo objects

    Example:
        >>> xml = fetch_citygml_from_plateau(35.681236, 139.767125)
        >>> buildings = parse_buildings_from_citygml(xml)
        >>> for b in buildings:
        ...     print(f"{b.building_id}: ({b.latitude}, {b.longitude})")
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"[PARSE] XML parse error: {e}")
        return []

    buildings: List[BuildingInfo] = []

    # Find all bldg:Building elements
    building_elements = root.findall(".//bldg:Building", NS)
    print(f"[PARSE] Found {len(building_elements)} building(s)")

    for building_elem in building_elements:
        # Extract gml:id (always present)
        gml_id = building_elem.get("{http://www.opengis.net/gml}id") or building_elem.get("id")
        if not gml_id:
            continue

        # Extract building ID (generic attribute - preferred)
        building_id = None
        for attr in building_elem.findall(".//gen:stringAttribute", NS):
            name = attr.get("name")
            if name in ["建物ID", "buildingID"]:
                value_elem = attr.find("./gen:value", NS)
                if value_elem is not None and value_elem.text:
                    building_id = value_elem.text.strip()
                    break

        # Extract coordinates (try multiple sources)
        coords = _extract_building_coordinates(building_elem)
        if not coords:
            continue

        lat, lon = coords

        # Extract height
        height = _extract_building_height(building_elem)

        # Extract usage
        usage_elem = building_elem.find(".//bldg:usage", NS)
        usage = usage_elem.text.strip() if usage_elem is not None and usage_elem.text else None

        # Extract measured height
        measured_height = None
        for tag in [".//bldg:measuredHeight", ".//uro:measuredHeight"]:
            elem = building_elem.find(tag, NS)
            if elem is not None and elem.text:
                try:
                    measured_height = float(elem.text)
                    break
                except ValueError:
                    pass

        # Extract building name
        name = None
        # Try gml:name first (standard CityGML tag)
        name_elem = building_elem.find(".//gml:name", NS)
        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()
        # Fall back to uro:buildingName (PLATEAU-specific extension)
        if not name:
            name_elem = building_elem.find(".//uro:buildingName", NS)
            if name_elem is not None and name_elem.text:
                name = name_elem.text.strip()

        buildings.append(BuildingInfo(
            building_id=building_id,
            gml_id=gml_id,
            latitude=lat,
            longitude=lon,
            distance_meters=0.0,  # Will be calculated later
            height=height,
            usage=usage,
            measured_height=measured_height,
            name=name
        ))

    print(f"[PARSE] Extracted {len(buildings)} valid building(s)")
    return buildings


def _extract_building_coordinates(building_elem: ET.Element) -> Optional[Tuple[float, float]]:
    """Extract representative coordinates for a building.

    Priority:
    1. lod0FootPrint
    2. lod0RoofEdge
    3. First posList in any geometry

    Returns:
        (latitude, longitude) tuple or None
    """
    # Try footprint/roof edge polygons
    for tag in [".//bldg:lod0FootPrint", ".//bldg:lod0RoofEdge"]:
        elem = building_elem.find(tag, NS)
        if elem is not None:
            poslist = elem.find(".//gml:posList", NS)
            if poslist is not None and poslist.text:
                coords = _parse_poslist(poslist)
                if coords:
                    # Return first coordinate
                    x, y, _ = coords[0]
                    # Check if this looks like lat/lon (WGS84)
                    if 20 <= x <= 50 and 120 <= y <= 155:
                        return (x, y)
                    elif 120 <= x <= 155 and 20 <= y <= 50:
                        return (y, x)  # Swapped

    # Fallback: any posList
    poslist = building_elem.find(".//gml:posList", NS)
    if poslist is not None and poslist.text:
        coords = _parse_poslist(poslist)
        if coords:
            x, y, _ = coords[0]
            # Guess order based on Japan coordinates
            if 20 <= x <= 50 and 120 <= y <= 155:
                return (x, y)
            elif 120 <= x <= 155 and 20 <= y <= 50:
                return (y, x)

    return None


def _parse_poslist(elem: ET.Element) -> List[Tuple[float, float, Optional[float]]]:
    """Parse gml:posList into list of (x, y, z) tuples."""
    txt = (elem.text or "").strip()
    if not txt:
        return []

    parts = txt.split()
    vals: List[float] = []
    for p in parts:
        try:
            vals.append(float(p))
        except ValueError:
            continue

    # Determine dimension (2D or 3D)
    dim = 3 if len(vals) % 3 == 0 and len(vals) >= 3 else 2
    coords: List[Tuple[float, float, Optional[float]]] = []

    if dim == 3:
        for i in range(0, len(vals), 3):
            coords.append((vals[i], vals[i + 1], vals[i + 2]))
    else:
        for i in range(0, len(vals), 2):
            if i + 1 < len(vals):
                coords.append((vals[i], vals[i + 1], None))

    return coords


def _extract_building_height(building_elem: ET.Element) -> Optional[float]:
    """Extract building height from various tags."""
    tags = [
        ".//bldg:measuredHeight",
        ".//uro:measuredHeight",
        ".//uro:buildingHeight",
    ]

    for tag in tags:
        elem = building_elem.find(tag, NS)
        if elem is not None and elem.text:
            try:
                height = float(elem.text)
                if height > 0:
                    return height
            except ValueError:
                continue

    return None


def find_nearest_building(
    buildings: List[BuildingInfo],
    target_latitude: float,
    target_longitude: float,
    query: Optional[str] = None
) -> List[BuildingInfo]:
    """Find and rank buildings by distance from target point.

    Simple approach: Sort by distance only (nearest building wins).

    Process:
    1. Calculate distances from target point
    2. Deduplicate by gml_id (removes duplicates)
    3. Sort by distance (ascending)

    Args:
        buildings: List of BuildingInfo objects
        target_latitude: Target latitude
        target_longitude: Target longitude
        query: Original search query (unused, kept for API compatibility)

    Returns:
        List of BuildingInfo sorted by distance (nearest first),
        with distance_meters field updated

    Example:
        >>> buildings = parse_buildings_from_citygml(xml)
        >>> sorted_buildings = find_nearest_building(buildings, 35.681236, 139.767125)
        >>> nearest = sorted_buildings[0]
        >>> print(f"Nearest: {nearest.building_id} at {nearest.distance_meters:.1f}m")
    """
    target_point = Point(target_longitude, target_latitude)

    # Step 1: Calculate distances for all buildings
    for building in buildings:
        building_point = Point(building.longitude, building.latitude)
        dist_degrees = distance(target_point, building_point)
        building.distance_meters = float(dist_degrees) * 100000  # Rough conversion

    # Step 2: Deduplicate by gml_id (keep first occurrence)
    # Also filter out buildings with unknown/invalid height (-9999 is PLATEAU's sentinel value)
    seen_ids = set()
    unique_buildings = []
    duplicates_removed = 0
    unknown_height_removed = 0

    for building in buildings:
        # Skip if duplicate
        if building.gml_id in seen_ids:
            duplicates_removed += 1
            continue

        # Skip buildings with unknown height (sentinel value -9999)
        height = building.measured_height or building.height or 0
        if height < 0:  # Negative heights are invalid (including -9999 sentinel)
            unknown_height_removed += 1
            continue

        seen_ids.add(building.gml_id)
        unique_buildings.append(building)

    if duplicates_removed > 0:
        print(f"[DEDUP] Removed {duplicates_removed} duplicate building(s)")
    if unknown_height_removed > 0:
        print(f"[FILTER] Removed {unknown_height_removed} building(s) with unknown height")

    # Step 3: Sort by distance (simplest approach - nearest building wins)
    unique_buildings.sort(key=lambda b: b.distance_meters)

    print(f"[SORT] Sorted {len(unique_buildings)} unique building(s) by distance")
    if unique_buildings:
        nearest = unique_buildings[0]
        height_str = f"{nearest.measured_height or nearest.height or 'unknown'}m"
        print(f"[SORT] Nearest building: {nearest.building_id or nearest.gml_id[:20]}")
        print(f"[SORT]   Distance: {nearest.distance_meters:.1f}m, Height: {height_str}")

    return unique_buildings


def search_buildings_by_address(
    query: str,
    radius: float = 0.001,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """High-level function: Search buildings by address/facility name.

    This function combines all steps:
    1. Geocode address to coordinates
    2. Fetch CityGML from PLATEAU
    3. Parse buildings
    4. Sort by distance

    Args:
        query: Address or facility name
        radius: Search radius in degrees (default: 0.001 ≈ 100m)
        limit: Maximum number of buildings to return

    Returns:
        Dictionary with:
        - success: bool
        - geocoding: GeocodingResult or None
        - buildings: List[BuildingInfo] sorted by distance
        - citygml_xml: str (CityGML XML content, only if success=True)
        - error: str (if success=False)

    Example:
        >>> result = search_buildings_by_address("東京駅", radius=0.001, limit=10)
        >>> if result["success"]:
        ...     for building in result["buildings"]:
        ...         print(f"{building.building_id}: {building.distance_meters:.1f}m")
    """
    print(f"\n{'='*60}")
    print(f"[SEARCH] Query: {query}")
    print(f"[SEARCH] Radius: {radius} degrees (~{radius*100000:.0f}m)")
    print(f"{'='*60}\n")

    # Step 1: Geocode
    geocoding = geocode_address(query)
    if not geocoding:
        return {
            "success": False,
            "geocoding": None,
            "buildings": [],
            "citygml_xml": None,
            "error": f"Address not found: {query}"
        }

    # Step 2: Fetch CityGML
    xml_content = fetch_citygml_from_plateau(
        geocoding.latitude,
        geocoding.longitude,
        radius=radius
    )
    if not xml_content:
        return {
            "success": False,
            "geocoding": geocoding,
            "buildings": [],
            "citygml_xml": None,
            "error": "Failed to fetch CityGML data from PLATEAU"
        }

    # Step 3: Parse buildings
    buildings = parse_buildings_from_citygml(xml_content)
    if not buildings:
        return {
            "success": False,
            "geocoding": geocoding,
            "buildings": [],
            "citygml_xml": xml_content,  # Include XML even if no buildings parsed
            "error": "No buildings found in PLATEAU data"
        }

    # Step 4: Sort by distance
    sorted_buildings = find_nearest_building(
        buildings,
        geocoding.latitude,
        geocoding.longitude
    )

    # Apply limit
    if limit is not None and limit > 0:
        sorted_buildings = sorted_buildings[:limit]

    print(f"\n{'='*60}")
    print(f"[SEARCH] Success: Found {len(sorted_buildings)} building(s)")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "geocoding": geocoding,
        "buildings": sorted_buildings,
        "citygml_xml": xml_content,  # Include fetched XML to avoid re-fetching
        "error": None
    }


if __name__ == "__main__":
    # Test with Tokyo Station
    result = search_buildings_by_address("東京駅", radius=0.001, limit=5)

    if result["success"]:
        print("\n" + "="*60)
        print("SEARCH RESULTS")
        print("="*60)

        geocoding = result["geocoding"]
        print(f"\nGeocoded Location:")
        print(f"  Query: {geocoding.query}")
        print(f"  Address: {geocoding.display_name}")
        print(f"  Coordinates: ({geocoding.latitude}, {geocoding.longitude})")

        print(f"\nBuildings Found: {len(result['buildings'])}")
        for i, building in enumerate(result["buildings"], 1):
            print(f"\n{i}. Building ID: {building.building_id or 'N/A'}")
            print(f"   gml:id: {building.gml_id}")
            print(f"   Distance: {building.distance_meters:.1f}m")
            print(f"   Height: {building.height or building.measured_height or 'N/A'}m")
            print(f"   Usage: {building.usage or 'N/A'}")
            print(f"   Coordinates: ({building.latitude}, {building.longitude})")
    else:
        print(f"\nError: {result['error']}")
