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
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import requests
from shapely.geometry import Point
from shapely import distance


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
    """
    building_id: Optional[str]
    gml_id: str
    latitude: float
    longitude: float
    distance_meters: float
    height: Optional[float] = None
    usage: Optional[str] = None
    measured_height: Optional[float] = None


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

    Example:
        >>> result = geocode_address("東京駅")
        >>> if result:
        ...     print(f"Found: {result.display_name}")
        ...     print(f"Coordinates: ({result.latitude}, {result.longitude})")
    """
    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"

    # Request parameters
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
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
            return None

        result = data[0]

        geocoding_result = GeocodingResult(
            query=query,
            latitude=float(result["lat"]),
            longitude=float(result["lon"]),
            display_name=result.get("display_name", ""),
            osm_type=result.get("osm_type"),
            osm_id=result.get("osm_id")
        )

        print(f"[GEOCODING] Success: {query} -> ({geocoding_result.latitude}, {geocoding_result.longitude})")
        print(f"[GEOCODING] Address: {geocoding_result.display_name}")

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


def fetch_citygml_from_plateau(
    latitude: float,
    longitude: float,
    radius: float = 0.001,
    timeout: int = 30
) -> Optional[str]:
    """Fetch CityGML data from PLATEAU Data Catalog API.

    Args:
        latitude: Center latitude (WGS84)
        longitude: Center longitude (WGS84)
        radius: Search radius in degrees (default: 0.001 ≈ 100m)
        timeout: Request timeout in seconds

    Returns:
        CityGML XML content as string if successful, None otherwise

    API Format:
        https://api.plateauview.mlit.go.jp/datacatalog/citygml/r:lon1,lat1,lon2,lat2

        Note: Order is lon,lat (not lat,lon)

    Example:
        >>> xml = fetch_citygml_from_plateau(35.681236, 139.767125, radius=0.001)
        >>> if xml:
        ...     print(f"Fetched {len(xml)} bytes of CityGML data")
    """
    # Calculate bounding box
    lon1 = longitude - radius
    lat1 = latitude - radius
    lon2 = longitude + radius
    lat2 = latitude + radius

    # PLATEAU API endpoint (note: lon,lat order!)
    url = f"https://api.plateauview.mlit.go.jp/datacatalog/citygml/r:{lon1},{lat1},{lon2},{lat2}"

    print(f"[PLATEAU] Fetching CityGML for bbox: ({lat1},{lon1}) to ({lat2},{lon2})")
    print(f"[PLATEAU] URL: {url}")

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        xml_content = response.text

        # Validate that we got XML
        if not xml_content or not xml_content.strip().startswith("<?xml"):
            print(f"[PLATEAU] Invalid response (not XML)")
            return None

        print(f"[PLATEAU] Success: Fetched {len(xml_content)} bytes")
        return xml_content

    except requests.exceptions.RequestException as e:
        print(f"[PLATEAU] Request failed: {e}")
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

        buildings.append(BuildingInfo(
            building_id=building_id,
            gml_id=gml_id,
            latitude=lat,
            longitude=lon,
            distance_meters=0.0,  # Will be calculated later
            height=height,
            usage=usage,
            measured_height=measured_height
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
    target_longitude: float
) -> List[BuildingInfo]:
    """Find and sort buildings by distance from target coordinates.

    Args:
        buildings: List of BuildingInfo objects
        target_latitude: Target latitude
        target_longitude: Target longitude

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

    # Calculate distances
    for building in buildings:
        building_point = Point(building.longitude, building.latitude)
        # distance() returns distance in degrees, convert to meters (rough)
        dist_degrees = distance(target_point, building_point)
        # At equator: 1 degree ≈ 111,000 meters
        # In Japan (lat ~35): 1 degree lat ≈ 111,000m, 1 degree lon ≈ 91,000m
        # Use average for rough estimate
        building.distance_meters = float(dist_degrees) * 100000  # Rough conversion

    # Sort by distance
    sorted_buildings = sorted(buildings, key=lambda b: b.distance_meters)

    print(f"[DISTANCE] Sorted {len(sorted_buildings)} building(s) by distance")
    if sorted_buildings:
        nearest = sorted_buildings[0]
        print(f"[DISTANCE] Nearest: {nearest.building_id or nearest.gml_id} at {nearest.distance_meters:.1f}m")

    return sorted_buildings


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
            "error": "Failed to fetch CityGML data from PLATEAU"
        }

    # Step 3: Parse buildings
    buildings = parse_buildings_from_citygml(xml_content)
    if not buildings:
        return {
            "success": False,
            "geocoding": geocoding,
            "buildings": [],
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
