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

import glob
import json
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Set

import requests
from shapely.geometry import Point
from shapely import distance

# Import mesh code utilities
import sys
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


# ============================================================================
# CityGML Cache Utilities (optional opt-in feature)
# ============================================================================

# Module-level cache for mesh index (loaded once per process)
_MESH_INDEX_CACHE: Optional[Dict[str, Any]] = None


def _get_cache_config() -> Dict[str, Any]:
    """Get CityGML cache configuration from environment variables.

    Returns:
        Dictionary with cache configuration:
        - enabled: bool - Whether cache is enabled
        - cache_dir: Path - Cache directory path
        - mesh_index_path: Path - Path to mesh_to_ward_index.json
    """
    cache_dir_str = os.getenv("CITYGML_CACHE_DIR", "backend/data/citygml_cache")
    cache_dir = Path(cache_dir_str)

    return {
        "enabled": os.getenv("CITYGML_CACHE_ENABLED", "false").lower() == "true",
        "cache_dir": cache_dir,
        "mesh_index_path": cache_dir / "mesh_to_ward_index.json"
    }


def _load_mesh_index() -> Dict[str, Any]:
    """Load mesh→ward index from cache with module-level caching.

    The index is loaded once per process and cached in memory for O(1) lookups.

    Returns:
        Dictionary mapping mesh codes to ward area codes:
        - Single ward: {"53393580": "13101"}
        - Multiple wards: {"53393580": ["13101", "13102"]}
        Empty dict if cache is disabled or loading fails.
    """
    global _MESH_INDEX_CACHE

    # Return cached index if already loaded
    if _MESH_INDEX_CACHE is not None:
        return _MESH_INDEX_CACHE

    config = _get_cache_config()
    if not config["enabled"]:
        _MESH_INDEX_CACHE = {}
        return _MESH_INDEX_CACHE

    try:
        mesh_index_path = config["mesh_index_path"]
        if not mesh_index_path.exists():
            print(f"[CACHE] Mesh index not found: {mesh_index_path}")
            _MESH_INDEX_CACHE = {}
            return _MESH_INDEX_CACHE

        with open(mesh_index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _MESH_INDEX_CACHE = data.get("index", {})
            print(f"[CACHE] Loaded mesh index with {len(_MESH_INDEX_CACHE)} entries")
            return _MESH_INDEX_CACHE

    except Exception as e:
        print(f"[CACHE] Failed to load mesh index: {e}")
        _MESH_INDEX_CACHE = {}
        return _MESH_INDEX_CACHE


def _get_ward_from_mesh(mesh_code: str) -> Optional[str]:
    """Get ward area code from mesh code using O(1) index lookup.

    Args:
        mesh_code: 3rd mesh code (8 digits, e.g., "53393580")

    Returns:
        Ward area code (e.g., "13101") if found, None otherwise.
        If mesh spans multiple wards, returns the first ward.
    """
    mesh_index = _load_mesh_index()
    ward = mesh_index.get(mesh_code)

    if ward is None:
        return None

    # Handle meshes spanning multiple wards
    if isinstance(ward, list):
        return ward[0] if ward else None

    return ward


def _get_wards_from_mesh(mesh_code: str) -> List[str]:
    """Get all ward area codes for a mesh code."""
    mesh_index = _load_mesh_index()
    ward = mesh_index.get(mesh_code)

    if ward is None:
        return []

    if isinstance(ward, list):
        return [w for w in ward if w]

    return [ward]


def _find_cached_gml_files(cache_dir: Path, area_code: str, mesh_code: str) -> List[Path]:
    """Find cached GML files for a mesh code within a ward directory."""
    # Find ward directory: {area_code}_*
    ward_dirs = list(cache_dir.glob(f"{area_code}_*"))
    if not ward_dirs:
        print(f"[CACHE] No ward directory found for area code: {area_code}")
        return []

    ward_dir = ward_dirs[0]

    # Find GML files matching the mesh code: {mesh_code}_bldg_*.gml
    gml_pattern = str(ward_dir / "udx" / "bldg" / f"{mesh_code}_bldg_*.gml")
    gml_files = [Path(p) for p in glob.glob(gml_pattern)]

    if not gml_files:
        print(f"[CACHE] No GML files found for mesh {mesh_code} in {ward_dir.name}")
        return []

    print(f"[CACHE] Found {len(gml_files)} GML file(s) for mesh {mesh_code} in {ward_dir.name}")
    return gml_files


def _load_gml_from_cache(mesh_code: str, area_code: str) -> Optional[str]:
    """Load CityGML content from cache for a specific mesh code.

    Args:
        mesh_code: 3rd mesh code (8 digits, e.g., "53393580")
        area_code: Ward area code (5 digits, e.g., "13101")

    Returns:
        Combined CityGML XML content as string if found, None otherwise.
    """
    config = _get_cache_config()
    cache_dir = config["cache_dir"]

    gml_files = _find_cached_gml_files(cache_dir, area_code, mesh_code)
    if not gml_files:
        return None

    # Single file: read directly
    if len(gml_files) == 1:
        try:
            with open(gml_files[0], 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[CACHE] Failed to read GML file: {e}")
            return None

    # Multiple files: combine them
    try:
        return _combine_gml_files(gml_files)
    except Exception as e:
        print(f"[CACHE] Failed to combine GML files: {e}")
        return None


def _load_gml_from_cache_multi(mesh_code: str, area_codes: List[str]) -> Optional[str]:
    """Load CityGML content from cache across multiple ward directories."""
    config = _get_cache_config()
    cache_dir = config["cache_dir"]

    all_files: List[Path] = []
    for area_code in area_codes:
        all_files.extend(_find_cached_gml_files(cache_dir, area_code, mesh_code))

    if not all_files:
        return None

    seen: Set[str] = set()
    unique_files: List[Path] = []
    for path in all_files:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique_files.append(path)

    print(f"[CACHE] Found {len(unique_files)} GML file(s) across wards for mesh {mesh_code}")

    if len(unique_files) == 1:
        try:
            with open(unique_files[0], 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[CACHE] Failed to read GML file: {e}")
            return None

    try:
        return _combine_gml_files(unique_files)
    except Exception as e:
        print(f"[CACHE] Failed to combine GML files: {e}")
        return None


def _combine_gml_files(file_paths: List[Path]) -> str:
    """Combine multiple CityGML files into a single XML document.

    Merges all cityObjectMember elements from multiple files into one root element.

    Args:
        file_paths: List of paths to CityGML files

    Returns:
        Combined CityGML XML content as string

    Raises:
        Exception if reading or parsing fails
    """
    if not file_paths:
        raise ValueError("No file paths provided")

    # Read base file
    with open(file_paths[0], 'r', encoding='utf-8') as f:
        base_xml = f.read()

    root = ET.fromstring(base_xml)

    # Single file: return as-is
    if len(file_paths) == 1:
        return base_xml

    # Merge remaining files
    for file_path in file_paths[1:]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        other_root = ET.fromstring(content)

        # Find all cityObjectMember elements and append to base
        for member in other_root.findall(".//{http://www.opengis.net/citygml/2.0}cityObjectMember"):
            root.append(member)

    # Convert back to string
    return ET.tostring(root, encoding='unicode')


# ============================================================================
# Name Matching Utilities (for building name search)
# ============================================================================

def calculate_name_similarity(building_name: Optional[str], query: Optional[str]) -> float:
    """Calculate similarity score between building name and search query.

    Uses multiple strategies for robust Japanese and English text matching:
    1. Exact match: 100% score
    2. Case-insensitive substring match: 80% score
    3. Levenshtein distance-based similarity: 0-70% score
    4. Partial token matching: Up to 60% score

    Args:
        building_name: Building name from CityGML (can be None)
        query: User search query (can be None)

    Returns:
        Similarity score from 0.0 (no match) to 1.0 (perfect match)

    Example:
        >>> calculate_name_similarity("東京駅", "東京駅")
        1.0
        >>> calculate_name_similarity("東京国際フォーラム", "東京")
        0.8  # Substring match
        >>> calculate_name_similarity("Tokyo Station", "tokyo")
        0.8  # Case-insensitive substring match
    """
    # Handle None or empty strings
    if not building_name or not query:
        return 0.0

    # Normalize strings (strip whitespace, lowercase for ASCII)
    name_lower = building_name.strip().lower()
    query_lower = query.strip().lower()

    # Strategy 1: Exact match (case-insensitive)
    if name_lower == query_lower:
        return 1.0

    # Strategy 2: Substring match (case-insensitive)
    if query_lower in name_lower or name_lower in query_lower:
        # Longer matches score higher
        overlap = min(len(query_lower), len(name_lower))
        total = max(len(query_lower), len(name_lower))
        return 0.8 * (overlap / total)

    # Strategy 3: Levenshtein distance (simple implementation)
    distance = _levenshtein_distance(name_lower, query_lower)
    max_len = max(len(name_lower), len(query_lower))
    if max_len == 0:
        return 0.0

    # Convert distance to similarity (0-70% range)
    similarity = max(0.0, 1.0 - (distance / max_len))
    similarity = similarity * 0.7  # Scale to 0-70%

    # Strategy 4: Token-based matching (split by common separators)
    # Useful for multi-word names like "東京 国際 フォーラム" vs "東京"
    name_tokens = set(_tokenize(name_lower))
    query_tokens = set(_tokenize(query_lower))

    if name_tokens and query_tokens:
        intersection = name_tokens & query_tokens
        union = name_tokens | query_tokens
        token_similarity = len(intersection) / len(union) if union else 0.0
        similarity = max(similarity, token_similarity * 0.6)  # Up to 60% for token match

    return similarity


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings.

    Simple dynamic programming implementation for string edit distance.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Minimum number of single-character edits (insertions, deletions, substitutions)
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _tokenize(text: str) -> List[str]:
    """Tokenize text by splitting on common separators.

    Handles spaces, hyphens, underscores, and Japanese separators.

    Args:
        text: Input text

    Returns:
        List of tokens (non-empty strings)
    """
    import re
    # Split by spaces, hyphens, underscores, Japanese middle dot (・), etc.
    tokens = re.split(r'[\s\-_・]+', text)
    return [t for t in tokens if t]  # Filter out empty strings


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
        relevance_score: Composite relevance score (0.0-1.0, optional)
        name_similarity: Name matching score (0.0-1.0, optional)
        match_reason: Human-readable explanation of why this building matched (optional)
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
    relevance_score: Optional[float] = None
    name_similarity: Optional[float] = None
    match_reason: Optional[str] = None
    has_lod2: bool = False  # Does the building have LOD2 geometry?
    has_lod3: bool = False  # Does the building have LOD3 geometry?


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

    # Step 1.5: Check cache if enabled
    config = _get_cache_config()
    if config["enabled"]:
        try:
            area_codes = _get_wards_from_mesh(center_mesh)
            if area_codes:
                if len(area_codes) > 1:
                    print(f"[CACHE] Mesh {center_mesh} spans multiple wards: {area_codes}")
                    cached_xml = _load_gml_from_cache_multi(center_mesh, area_codes)
                else:
                    cached_xml = _load_gml_from_cache(center_mesh, area_codes[0])

                if cached_xml:
                    ward_label = area_codes if len(area_codes) > 1 else area_codes[0]
                    print(f"[PLATEAU] ✓ Cache HIT: mesh={center_mesh}, wards={ward_label}")
                    return cached_xml

                ward_label = area_codes if len(area_codes) > 1 else area_codes[0]
                print(f"[PLATEAU] Cache MISS: mesh={center_mesh}, wards={ward_label}")
        except Exception as e:
            print(f"[PLATEAU] Cache error (falling back to API): {e}")

    # Step 2: Query PLATEAU API with mesh code (fallback)
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

        # Extract building ID (try multiple sources)
        building_id = None

        # Try 1: uro:buildingIDAttribute/uro:BuildingIDAttribute/uro:buildingID (PLATEAU standard)
        # Format: <uro:buildingIDAttribute><uro:BuildingIDAttribute><uro:buildingID>13101-bldg-1234</uro:buildingID>...
        building_id_elem = building_elem.find(".//uro:buildingIDAttribute/uro:BuildingIDAttribute/uro:buildingID", NS)
        if building_id_elem is not None and building_id_elem.text:
            building_id = building_id_elem.text.strip()

        # Try 2: uro:buildingDetails/uro:buildingID (alternative location)
        if not building_id:
            building_id_elem = building_elem.find(".//uro:buildingDetails/uro:buildingID", NS)
            if building_id_elem is not None and building_id_elem.text:
                building_id = building_id_elem.text.strip()

        # Try 3: gen:stringAttribute (generic attribute)
        if not building_id:
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

        # Detect LOD levels
        has_lod2, has_lod3 = _detect_lod_levels(building_elem, building_id=building_id or gml_id)

        buildings.append(BuildingInfo(
            building_id=building_id,
            gml_id=gml_id,
            latitude=lat,
            longitude=lon,
            distance_meters=0.0,  # Will be calculated later
            height=height,
            usage=usage,
            measured_height=measured_height,
            name=name,
            has_lod2=has_lod2,
            has_lod3=has_lod3
        ))

    # Summary statistics
    lod3_count = sum(1 for b in buildings if b.has_lod3)
    lod2_count = sum(1 for b in buildings if b.has_lod2 and not b.has_lod3)
    lod1_count = len(buildings) - lod3_count - lod2_count

    print(f"[PARSE] Extracted {len(buildings)} valid building(s)")
    print(f"[PARSE] LOD Summary:")
    print(f"[PARSE]   - LOD3: {lod3_count} building(s) ({100*lod3_count/len(buildings) if buildings else 0:.1f}%)")
    print(f"[PARSE]   - LOD2: {lod2_count} building(s) ({100*lod2_count/len(buildings) if buildings else 0:.1f}%)")
    print(f"[PARSE]   - LOD1 or lower: {lod1_count} building(s) ({100*lod1_count/len(buildings) if buildings else 0:.1f}%)")

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


def _detect_lod_levels(building_elem: ET.Element, building_id: Optional[str] = None) -> Tuple[bool, bool]:
    """Detect which LOD levels are available for a building.

    Returns:
        (has_lod2, has_lod3) tuple of booleans

    Detection strategy:
    - LOD3: Check for lod3Solid, lod3MultiSurface, lod3Geometry, or detailed BoundarySurfaces
    - LOD2: Check for lod2Solid, lod2MultiSurface, lod2Geometry, or WallSurface/RoofSurface
    """
    has_lod3 = False
    has_lod2 = False
    found_tags = []

    building_label = building_id or building_elem.get("{http://www.opengis.net/gml}id", "unknown")[:30]
    print(f"[LOD DEBUG] Checking building: {building_label}")

    # Check LOD3 indicators
    lod3_tags = [
        ".//bldg:lod3Solid",
        ".//bldg:lod3MultiSurface",
        ".//bldg:lod3Geometry",
    ]
    print(f"[LOD DEBUG]   Searching for LOD3 tags: {[t.split(':')[1] for t in lod3_tags]}")
    for tag in lod3_tags:
        elem = building_elem.find(tag, NS)
        if elem is not None:
            has_lod3 = True
            tag_name = tag.split(":")[-1]
            found_tags.append(f"LOD3:{tag_name}")
            print(f"[LOD DEBUG]   ✓ Found LOD3 tag: {tag_name}")
            break

    # Check LOD2 indicators
    lod2_tags = [
        ".//bldg:lod2Solid",
        ".//bldg:lod2MultiSurface",
        ".//bldg:lod2Geometry",
    ]
    print(f"[LOD DEBUG]   Searching for LOD2 tags: {[t.split(':')[1] for t in lod2_tags]}")
    for tag in lod2_tags:
        elem = building_elem.find(tag, NS)
        if elem is not None:
            has_lod2 = True
            tag_name = tag.split(":")[-1]
            found_tags.append(f"LOD2:{tag_name}")
            print(f"[LOD DEBUG]   ✓ Found LOD2 tag: {tag_name}")
            break

    # Alternative detection: Check for BoundarySurface types
    # LOD2/LOD3 buildings typically have WallSurface and RoofSurface
    if not has_lod2 and not has_lod3:
        print(f"[LOD DEBUG]   No direct LOD2/LOD3 tags found, checking BoundarySurfaces...")
        boundary_tags = [
            ".//bldg:WallSurface",
            ".//bldg:RoofSurface",
        ]
        for tag in boundary_tags:
            elem = building_elem.find(tag, NS)
            if elem is not None:
                has_lod2 = True  # At least LOD2
                tag_name = tag.split(":")[-1]
                found_tags.append(f"Boundary:{tag_name}")
                print(f"[LOD DEBUG]   ✓ Found boundary surface: {tag_name} (implies LOD2)")
                break

    # Final result
    result_str = []
    if has_lod3:
        result_str.append("LOD3")
    if has_lod2:
        result_str.append("LOD2")
    if not result_str:
        result_str.append("LOD1 or lower")

    print(f"[LOD DEBUG]   Result: {', '.join(result_str)} | Tags found: {found_tags or 'none'}")

    return (has_lod2, has_lod3)


def find_nearest_building(
    buildings: List[BuildingInfo],
    target_latitude: float,
    target_longitude: float,
    name_query: Optional[str] = None,
    search_mode: str = "hybrid"
) -> List[BuildingInfo]:
    """Find and rank buildings by composite relevance score.

    Smart ranking approach that combines distance and name similarity:
    - "distance": Sort by distance only (legacy behavior)
    - "name": Sort by name similarity only (requires name_query)
    - "hybrid": Combine distance (50%) + name similarity (50%) [DEFAULT]

    Process:
    1. Calculate distances from target point
    2. Calculate name similarity scores (if name_query provided)
    3. Compute composite relevance score based on search_mode
    4. Deduplicate by gml_id (removes duplicates)
    5. Sort by relevance score (descending) or distance (ascending)

    Args:
        buildings: List of BuildingInfo objects
        target_latitude: Target latitude
        target_longitude: Target longitude
        name_query: Building name to search for (optional)
        search_mode: Ranking strategy - "distance", "name", or "hybrid" (default)

    Returns:
        List of BuildingInfo sorted by relevance (best match first),
        with distance_meters, name_similarity, relevance_score, and match_reason fields updated

    Example:
        >>> buildings = parse_buildings_from_citygml(xml)
        >>> # Distance-only search
        >>> sorted_buildings = find_nearest_building(buildings, 35.681236, 139.767125, search_mode="distance")
        >>> # Name-based search
        >>> sorted_buildings = find_nearest_building(buildings, 35.681236, 139.767125, name_query="東京駅", search_mode="name")
        >>> # Hybrid search (best of both)
        >>> sorted_buildings = find_nearest_building(buildings, 35.681236, 139.767125, name_query="東京駅", search_mode="hybrid")
    """
    target_point = Point(target_longitude, target_latitude)

    # Validate search_mode
    valid_modes = ["distance", "name", "hybrid"]
    if search_mode not in valid_modes:
        print(f"[RANK] Invalid search_mode '{search_mode}', defaulting to 'hybrid'")
        search_mode = "hybrid"

    # If name mode but no query, fall back to distance mode
    if search_mode == "name" and not name_query:
        print(f"[RANK] Name search mode requires name_query, falling back to distance mode")
        search_mode = "distance"

    print(f"[RANK] Search mode: {search_mode}")
    if name_query:
        print(f"[RANK] Name query: '{name_query}'")

    # Step 1: Calculate distances and normalize (0.0 = far, 1.0 = very close)
    max_distance = 0.0
    for building in buildings:
        building_point = Point(building.longitude, building.latitude)
        dist_degrees = distance(target_point, building_point)
        building.distance_meters = float(dist_degrees) * 100000  # Rough conversion
        max_distance = max(max_distance, building.distance_meters)

    # Normalize distances to 0-1 range (inverse: closer = higher score)
    distance_scores = {}
    for building in buildings:
        if max_distance > 0:
            # Inverse normalized distance (1.0 = closest, 0.0 = farthest)
            distance_scores[building.gml_id] = 1.0 - (building.distance_meters / max_distance)
        else:
            distance_scores[building.gml_id] = 1.0

    # Step 2: Calculate name similarity scores (if applicable)
    name_scores = {}
    has_name_matches = False
    if name_query:
        for building in buildings:
            similarity = calculate_name_similarity(building.name, name_query)
            name_scores[building.gml_id] = similarity
            building.name_similarity = similarity
            if similarity > 0.3:  # Threshold for "significant" match
                has_name_matches = True

        print(f"[RANK] Found {sum(1 for s in name_scores.values() if s > 0.3)} building(s) with significant name matches")

    # Step 3: Compute composite relevance score
    for building in buildings:
        distance_score = distance_scores[building.gml_id]
        name_score = name_scores.get(building.gml_id, 0.0)

        if search_mode == "distance":
            # Distance only (legacy behavior)
            relevance = distance_score
            reason = f"Distance-based ({building.distance_meters:.1f}m away)"
        elif search_mode == "name":
            # Name only
            relevance = name_score
            if name_score > 0.0:
                reason = f"Name match (similarity: {name_score:.1%})"
            else:
                reason = "No name match"
        else:  # hybrid
            # Combine distance (50%) + name (50%)
            # If name query is provided but building has no name, penalize slightly
            if name_query and not building.name:
                relevance = distance_score * 0.5  # Only distance component
                reason = f"Distance only ({building.distance_meters:.1f}m away, no building name)"
            else:
                relevance = (distance_score * 0.5) + (name_score * 0.5)
                if name_score > 0.3:
                    reason = f"Name match ({name_score:.1%}) + Distance ({building.distance_meters:.1f}m)"
                elif name_score > 0.0:
                    reason = f"Weak name match ({name_score:.1%}) + Distance ({building.distance_meters:.1f}m)"
                else:
                    reason = f"Distance-based ({building.distance_meters:.1f}m away)"

        building.relevance_score = relevance
        building.match_reason = reason

    # Step 4: Deduplicate by gml_id (keep first occurrence)
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

    # Step 5: Sort by relevance score (descending) or distance (ascending)
    if search_mode == "distance":
        # Legacy behavior: sort by distance (ascending)
        unique_buildings.sort(key=lambda b: b.distance_meters)
        sort_desc = "distance (ascending)"
    else:
        # Sort by relevance score (descending - higher is better)
        unique_buildings.sort(key=lambda b: b.relevance_score or 0.0, reverse=True)
        sort_desc = "relevance score (descending)"

    print(f"[SORT] Sorted {len(unique_buildings)} unique building(s) by {sort_desc}")
    if unique_buildings:
        best = unique_buildings[0]
        height_str = f"{best.measured_height or best.height or 'unknown'}m"
        name_str = f'"{best.name}"' if best.name else "unnamed"
        print(f"[SORT] Best match: {best.building_id or best.gml_id[:20]}")
        print(f"[SORT]   Name: {name_str}, Height: {height_str}")
        print(f"[SORT]   Distance: {best.distance_meters:.1f}m, Relevance: {best.relevance_score:.3f}")
        print(f"[SORT]   Reason: {best.match_reason}")

    return unique_buildings


def search_buildings_by_address(
    query: str,
    radius: float = 0.001,
    limit: Optional[int] = None,
    name_filter: Optional[str] = None,
    search_mode: str = "hybrid"
) -> Dict[str, Any]:
    """High-level function: Search buildings by address/facility name with smart ranking.

    This function combines all steps:
    1. Geocode address to coordinates
    2. Fetch CityGML from PLATEAU
    3. Parse buildings
    4. Smart ranking by distance + name similarity (configurable)

    Args:
        query: Address or facility name
        radius: Search radius in degrees (default: 0.001 ≈ 100m)
        limit: Maximum number of buildings to return
        name_filter: Building name to search for (optional, for name-based ranking)
        search_mode: Ranking strategy - "distance", "name", or "hybrid" (default)

    Returns:
        Dictionary with:
        - success: bool
        - geocoding: GeocodingResult or None
        - buildings: List[BuildingInfo] sorted by relevance
        - citygml_xml: str (CityGML XML content, only if success=True)
        - error: str (if success=False)
        - search_mode: str (the mode used for ranking)

    Example:
        >>> # Distance-only search (legacy)
        >>> result = search_buildings_by_address("東京駅", radius=0.001, limit=10, search_mode="distance")
        >>> # Name-based search
        >>> result = search_buildings_by_address("千代田区", radius=0.01, limit=20, name_filter="東京駅", search_mode="name")
        >>> # Hybrid search (recommended)
        >>> result = search_buildings_by_address("東京駅", radius=0.001, limit=10, name_filter="東京駅", search_mode="hybrid")
        >>> if result["success"]:
        ...     for building in result["buildings"]:
        ...         print(f"{building.building_id}: {building.match_reason}")
    """
    # 渋谷フクラスの特別処理（ハードコーディング）
    if "フクラス" in query or "fukuras" in query.lower():
        print(f"\n{'='*60}")
        print(f"[SEARCH] Detected Shibuya Fukuras query - using hardcoded mesh/building ID")
        print(f"[SEARCH] Mesh code: 53393586, Building ID: bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674")
        print(f"{'='*60}\n")

        # 既存の search_building_by_id_and_mesh() 関数を使用
        result = search_building_by_id_and_mesh(
            building_id="bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674",
            mesh_code="53393586",
            debug=False
        )

        if result["success"] and result["building"]:
            # 渋谷フクラスの座標でGeocodingResultを作成
            geocoding = GeocodingResult(
                query=query,
                latitude=35.65806,  # 渋谷フクラスの座標
                longitude=139.70028,
                display_name="渋谷フクラス (Shibuya Fukuras), 2-chōme-24-12 Dōgenzaka, Shibuya City, Tokyo",
                osm_type="hardcoded",
                osm_id=0
            )

            # 建物情報を返す
            building = result["building"]
            building.name = "渋谷フクラス"  # 名前を設定
            building.match_reason = "完全一致"
            building.relevance_score = 1.0
            building.name_similarity = 1.0

            # limitを適用（通常は1件だけ）
            buildings = [building]
            if limit is not None and limit > 0:
                buildings = buildings[:limit]

            print(f"\n{'='*60}")
            print(f"[SEARCH] Success: Found Shibuya Fukuras (hardcoded)")
            print(f"[SEARCH] Building ID: {building.gml_id}")
            print(f"{'='*60}\n")

            return {
                "success": True,
                "geocoding": geocoding,
                "buildings": buildings,
                "citygml_xml": result["citygml_xml"],
                "search_mode": search_mode,
                "error": None
            }
        else:
            # フォールバック：search_building_by_id_and_meshが失敗した場合は通常の検索に
            print(f"[SEARCH] WARNING: Hardcoded search failed, falling back to normal search")
            print(f"[SEARCH] Error: {result.get('error')}")

    print(f"\n{'='*60}")
    print(f"[SEARCH] Query: {query}")
    print(f"[SEARCH] Radius: {radius} degrees (~{radius*100000:.0f}m)")
    print(f"[SEARCH] Name filter: {name_filter or 'None'}")
    print(f"[SEARCH] Search mode: {search_mode}")
    print(f"{'='*60}\n")

    # Step 1: Geocode
    geocoding = geocode_address(query)
    if not geocoding:
        return {
            "success": False,
            "geocoding": None,
            "buildings": [],
            "citygml_xml": None,
            "search_mode": search_mode,
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
            "search_mode": search_mode,
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
            "search_mode": search_mode,
            "error": "No buildings found in PLATEAU data"
        }

    # Step 4: Smart ranking by distance + name similarity
    sorted_buildings = find_nearest_building(
        buildings,
        geocoding.latitude,
        geocoding.longitude,
        name_query=name_filter,
        search_mode=search_mode
    )

    # Apply limit
    if limit is not None and limit > 0:
        sorted_buildings = sorted_buildings[:limit]

    print(f"\n{'='*60}")
    print(f"[SEARCH] Success: Found {len(sorted_buildings)} building(s)")
    if sorted_buildings:
        best = sorted_buildings[0]
        print(f"[SEARCH] Top result: {best.name or best.gml_id[:30]}")
        print(f"[SEARCH]   Relevance: {best.relevance_score:.3f}, Reason: {best.match_reason}")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "geocoding": geocoding,
        "buildings": sorted_buildings,
        "citygml_xml": xml_content,  # Include fetched XML to avoid re-fetching
        "search_mode": search_mode,
        "error": None
    }


def extract_municipality_code(building_id: str) -> Optional[str]:
    """Extract municipality code from building ID.

    PLATEAU building IDs typically follow the format: {municipality_code}-bldg-{number}
    Example: "13101-bldg-2287" -> "13101" (Chiyoda-ku, Tokyo)

    Args:
        building_id: Building ID string

    Returns:
        5-digit municipality code if found, None otherwise
    """
    if not building_id or not isinstance(building_id, str):
        return None

    # Extract first part before "-bldg-"
    parts = building_id.split("-")
    if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 5:
        return parts[0]

    return None


def _get_municipality_name_from_code(municipality_code: str) -> Optional[str]:
    """Get municipality name from code using a mapping of major municipalities.

    For comprehensive coverage, this uses geocoding as fallback.
    """
    # Tokyo special wards (23区)
    tokyo_wards = {
        "13101": "千代田区", "13102": "中央区", "13103": "港区",
        "13104": "新宿区", "13105": "文京区", "13106": "台東区",
        "13107": "墨田区", "13108": "江東区", "13109": "品川区",
        "13110": "目黒区", "13111": "大田区", "13112": "世田谷区",
        "13113": "渋谷区", "13114": "中野区", "13115": "杉並区",
        "13116": "豊島区", "13117": "北区", "13118": "荒川区",
        "13119": "板橋区", "13120": "練馬区", "13121": "足立区",
        "13122": "葛飾区", "13123": "江戸川区",
    }

    return tokyo_wards.get(municipality_code)


def fetch_citygml_by_municipality(municipality_code: str, timeout: int = 30) -> Optional[Tuple[str, str, int]]:
    """Fetch CityGML data from PLATEAU using municipality code.

    Strategy:
    1. Get municipality name from code
    2. Geocode municipality city hall to get coordinates
    3. Calculate mesh codes (center + neighbors) to cover the municipality
    4. Download CityGML files using mesh code search (m:)
    5. Combine into single XML document

    Args:
        municipality_code: 5-digit municipality code (e.g., "13113" for Shibuya-ku)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (xml_content, municipality_name, total_buildings) if successful, None otherwise
    """
    print(f"[PLATEAU] Fetching CityGML for municipality: {municipality_code}")

    # Step 1: Get municipality name
    municipality_name = _get_municipality_name_from_code(municipality_code)
    if not municipality_name:
        print(f"[PLATEAU] Municipality code {municipality_code} not found in mapping")
        return None

    print(f"[PLATEAU] Municipality: {municipality_name}")

    # Step 1.5: Check if entire ward is cached
    config = _get_cache_config()
    if config["enabled"]:
        try:
            cache_dir = config["cache_dir"]
            ward_dirs = list(cache_dir.glob(f"{municipality_code}_*"))
            if ward_dirs:
                ward_dir = ward_dirs[0]
                ward_metadata_path = ward_dir / "ward_metadata.json"

                if ward_metadata_path.exists():
                    with open(ward_metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    # Load all GML files for this ward
                    all_gml_files = []
                    for mesh_code in metadata.get("mesh_codes", []):
                        gml_pattern = str(ward_dir / "udx" / "bldg" / f"{mesh_code}_bldg_*.gml")
                        all_gml_files.extend(glob.glob(gml_pattern))

                    if all_gml_files:
                        print(f"[PLATEAU] ✓ Cache HIT: Full ward cached ({len(all_gml_files)} files)")
                        combined_xml = _combine_gml_files([Path(f) for f in all_gml_files])

                        # Count buildings in combined XML
                        try:
                            root = ET.fromstring(combined_xml)
                            buildings = root.findall(".//{http://www.opengis.net/citygml/building/2.0}Building")
                            total_buildings = len(buildings)
                            print(f"[PLATEAU] Cache: Found {total_buildings} buildings in {municipality_name}")
                            return (combined_xml, municipality_name, total_buildings)
                        except ET.ParseError as e:
                            print(f"[PLATEAU] Cache: Failed to parse combined XML: {e}")
                            # Fall through to API download
        except Exception as e:
            print(f"[PLATEAU] Cache error (falling back to API): {e}")

    # Step 2: Geocode city hall to get representative coordinates (fallback)
    geocode_query = f"{municipality_name}役所"
    geocoding = geocode_address(geocode_query)

    if not geocoding:
        print(f"[PLATEAU] Failed to geocode municipality: {geocode_query}")
        return None

    print(f"[PLATEAU] Center coordinates: ({geocoding.latitude}, {geocoding.longitude})")

    # Step 3: Calculate mesh codes (center + neighbors for wider coverage)
    try:
        center_mesh = latlon_to_mesh_3rd(geocoding.latitude, geocoding.longitude)
        print(f"[PLATEAU] Center mesh: {center_mesh}")

        # Get neighboring meshes (3x3 grid = 9 meshes total, covering ~3km x 3km)
        mesh_codes = get_neighboring_meshes_3rd(center_mesh)
        print(f"[PLATEAU] Searching {len(mesh_codes)} mesh(es) to cover municipality")
    except Exception as e:
        print(f"[PLATEAU] Failed to calculate mesh codes: {e}")
        return None

    # Step 4: Query PLATEAU API for each mesh and collect CityGML URLs
    all_citygml_urls = []
    MAX_MESHES = 9  # Limit to center + 8 neighbors
    MAX_FILES_PER_MESH = 5  # Limit files per mesh

    for i, mesh_code in enumerate(mesh_codes[:MAX_MESHES]):
        api_url = f"https://api.plateauview.mlit.go.jp/datacatalog/citygml/m:{mesh_code}"
        print(f"[PLATEAU] Mesh {i+1}/{min(len(mesh_codes), MAX_MESHES)}: {mesh_code}")

        try:
            response = requests.get(api_url, timeout=timeout)
            response.raise_for_status()
            catalog_data = response.json()

            # Extract building CityGML file URLs
            if "cities" in catalog_data:
                for city in catalog_data["cities"]:
                    city_name = city.get("cityName", "Unknown")
                    files = city.get("files", {})
                    bldg_files = files.get("bldg", [])

                    print(f"[PLATEAU]   {city_name}: {len(bldg_files)} building file(s)")

                    for bldg_file in bldg_files[:MAX_FILES_PER_MESH]:
                        url = bldg_file.get("url")
                        if url and url not in all_citygml_urls:  # Deduplicate
                            all_citygml_urls.append(url)

        except requests.exceptions.RequestException as e:
            print(f"[PLATEAU]   API request failed: {e}")
            # Continue with next mesh
            continue
        except ValueError as e:
            print(f"[PLATEAU]   Invalid JSON response: {e}")
            continue

    if not all_citygml_urls:
        print(f"[PLATEAU] No CityGML files found for {municipality_name}")
        return None

    print(f"[PLATEAU] Downloading {len(all_citygml_urls)} CityGML file(s)...")

    # Step 5: Download and combine CityGML files
    combined_xml = _download_and_combine_citygml(all_citygml_urls, timeout=timeout)

    if not combined_xml:
        print(f"[PLATEAU] Failed to download CityGML files")
        return None

    # Count total buildings in XML
    try:
        root = ET.fromstring(combined_xml)
        buildings = root.findall(".//{http://www.opengis.net/citygml/building/2.0}Building")
        total_buildings = len(buildings)
        print(f"[PLATEAU] Success: Found {total_buildings} total buildings in {municipality_name}")
    except ET.ParseError as e:
        print(f"[PLATEAU] Failed to parse combined XML: {e}")
        total_buildings = 0

    return (combined_xml, municipality_name, total_buildings)


def search_building_by_id(building_id: str, debug: bool = False) -> dict:
    """Search for a specific building by its ID in PLATEAU data.

    Args:
        building_id: Building ID (e.g., "13101-bldg-2287")
        debug: Enable debug logging

    Returns:
        Dictionary with search results:
        {
            "success": bool,
            "building": BuildingInfo or None,
            "municipality_code": str or None,
            "municipality_name": str or None,
            "citygml_file": str or None,
            "citygml_xml": str or None,
            "total_buildings_in_file": int or None,
            "error": str or None,
            "error_details": str or None
        }
    """
    print(f"\n{'='*60}")
    print(f"[BUILDING ID SEARCH] Searching for building: {building_id}")
    print(f"{'='*60}\n")

    # Step 1: Extract municipality code
    municipality_code = extract_municipality_code(building_id)
    if not municipality_code:
        return {
            "success": False,
            "building": None,
            "municipality_code": None,
            "municipality_name": None,
            "citygml_file": None,
            "citygml_xml": None,
            "total_buildings_in_file": None,
            "error": "Invalid building ID format",
            "error_details": f"Expected format: {{5-digit-code}}-bldg-{{number}}, got: {building_id}"
        }

    print(f"[BUILDING ID SEARCH] Extracted municipality code: {municipality_code}")

    # Step 2: Fetch CityGML for municipality
    fetch_result = fetch_citygml_by_municipality(municipality_code)
    if not fetch_result:
        return {
            "success": False,
            "building": None,
            "municipality_code": municipality_code,
            "municipality_name": None,
            "citygml_file": None,
            "citygml_xml": None,
            "total_buildings_in_file": None,
            "error": "Failed to fetch PLATEAU data",
            "error_details": f"No CityGML data found for municipality code: {municipality_code}"
        }

    xml_content, municipality_name, total_buildings = fetch_result
    print(f"[BUILDING ID SEARCH] Municipality: {municipality_name}, Total buildings: {total_buildings}")

    # Step 3: Parse buildings and find the target building
    buildings = parse_buildings_from_citygml(xml_content)
    if not buildings:
        return {
            "success": False,
            "building": None,
            "municipality_code": municipality_code,
            "municipality_name": municipality_name,
            "citygml_file": None,
            "citygml_xml": xml_content,
            "total_buildings_in_file": total_buildings,
            "error": "No buildings parsed from CityGML",
            "error_details": f"CityGML contained {total_buildings} buildings but none could be parsed successfully"
        }

    # Step 4: Find building by gml:id
    target_building = None
    for building in buildings:
        if building.gml_id == building_id or (building.building_id and building.building_id == building_id):
            target_building = building
            break

    if not target_building:
        # Try fuzzy match (case-insensitive, strip whitespace)
        building_id_normalized = building_id.strip().lower()
        for building in buildings:
            gml_id_normalized = building.gml_id.strip().lower() if building.gml_id else ""
            building_id_norm = building.building_id.strip().lower() if building.building_id else ""

            if gml_id_normalized == building_id_normalized or building_id_norm == building_id_normalized:
                target_building = building
                break

    if not target_building:
        # Collect similar IDs for error message
        similar_ids = [b.gml_id for b in buildings[:5]]
        return {
            "success": False,
            "building": None,
            "municipality_code": municipality_code,
            "municipality_name": municipality_name,
            "citygml_file": None,
            "citygml_xml": xml_content,
            "total_buildings_in_file": len(buildings),
            "error": f"Building not found",
            "error_details": f"Searched {len(buildings)} buildings in {municipality_name}, but building ID '{building_id}' was not found. Example IDs from this area: {', '.join(similar_ids[:3])}"
        }

    print(f"\n{'='*60}")
    print(f"[BUILDING ID SEARCH] Success: Found building!")
    print(f"[BUILDING ID SEARCH]   ID: {target_building.gml_id}")
    print(f"[BUILDING ID SEARCH]   Name: {target_building.name or 'N/A'}")
    print(f"[BUILDING ID SEARCH]   Height: {target_building.height or target_building.measured_height or 'N/A'}m")
    print(f"[BUILDING ID SEARCH]   LOD2: {target_building.has_lod2}, LOD3: {target_building.has_lod3}")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "building": target_building,
        "municipality_code": municipality_code,
        "municipality_name": municipality_name,
        "citygml_file": None,  # Could extract from URL if needed
        "citygml_xml": xml_content,
        "total_buildings_in_file": len(buildings),
        "error": None,
        "error_details": None
    }


def fetch_citygml_by_mesh_code(
    mesh_code: str,
    timeout: int = 30
) -> Optional[str]:
    """Fetch CityGML data from PLATEAU using mesh code directly.

    Args:
        mesh_code: 3rd mesh code (8 digits, 1km area, e.g., "53394511")
        timeout: Request timeout in seconds

    Returns:
        Combined CityGML XML content as string if successful, None otherwise

    Example:
        >>> xml = fetch_citygml_by_mesh_code("53394511")
        >>> if xml:
        ...     print(f"Fetched {len(xml)} bytes of CityGML data")
    """
    print(f"[PLATEAU] Fetching CityGML for mesh code: {mesh_code}")

    # Validate mesh code format (8 digits for 3rd mesh)
    if not mesh_code.isdigit() or len(mesh_code) != 8:
        print(f"[PLATEAU] Invalid mesh code format: {mesh_code} (expected 8 digits)")
        return None

    # Check cache if enabled
    config = _get_cache_config()
    if config["enabled"]:
        try:
            area_codes = _get_wards_from_mesh(mesh_code)
            if area_codes:
                if len(area_codes) > 1:
                    print(f"[CACHE] Mesh {mesh_code} spans multiple wards: {area_codes}")
                    cached_xml = _load_gml_from_cache_multi(mesh_code, area_codes)
                else:
                    cached_xml = _load_gml_from_cache(mesh_code, area_codes[0])

                if cached_xml:
                    ward_label = area_codes if len(area_codes) > 1 else area_codes[0]
                    print(f"[PLATEAU] ✓ Cache HIT: mesh={mesh_code}, wards={ward_label}")
                    return cached_xml

                ward_label = area_codes if len(area_codes) > 1 else area_codes[0]
                print(f"[PLATEAU] Cache MISS: mesh={mesh_code}, wards={ward_label}")
        except Exception as e:
            print(f"[PLATEAU] Cache error (falling back to API): {e}")

    # Query PLATEAU API with mesh code (fallback)
    api_url = f"https://api.plateauview.mlit.go.jp/datacatalog/citygml/m:{mesh_code}"

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

    # Extract building CityGML file URLs
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
        print(f"[PLATEAU] No CityGML files found for mesh code: {mesh_code}")
        return None

    if len(citygml_urls) > MAX_FILES:
        citygml_urls = citygml_urls[:MAX_FILES]
        print(f"[PLATEAU] Limited to {MAX_FILES} file(s) to prevent memory issues")

    print(f"[PLATEAU] Downloading {len(citygml_urls)} CityGML file(s)...")

    # Download and combine CityGML files
    combined_xml = _download_and_combine_citygml(citygml_urls, timeout=timeout)

    if combined_xml:
        print(f"[PLATEAU] Success: Combined {len(combined_xml)} bytes from {len(citygml_urls)} file(s)")
    else:
        print(f"[PLATEAU] Failed to download CityGML files")

    return combined_xml


def search_building_by_id_and_mesh(
    building_id: str,
    mesh_code: str,
    debug: bool = False
) -> dict:
    """Search for a specific building by GML ID + mesh code (optimized).

    This function is much faster than search_building_by_id() because it only
    downloads 1km² area instead of the entire municipality.

    Args:
        building_id: GML ID (e.g., "bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86")
                     or legacy building ID (e.g., "13101-bldg-2287")
        mesh_code: 3rd mesh code (8 digits, 1km area, e.g., "53394511")
        debug: Enable debug logging

    Returns:
        Dictionary with search results:
        {
            "success": bool,
            "building": BuildingInfo or None,
            "mesh_code": str,
            "citygml_xml": str or None,
            "total_buildings_in_mesh": int or None,
            "error": str or None,
            "error_details": str or None
        }

    Example:
        >>> result = search_building_by_id_and_mesh("bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86", "53394511")
        >>> if result["success"]:
        ...     print(f"Found: {result['building'].name}")
    """
    print(f"\n{'='*60}")
    print(f"[BUILDING SEARCH] Building ID: {building_id}, Mesh Code: {mesh_code}")
    print(f"{'='*60}\n")

    # Step 1: Validate mesh code
    if not mesh_code.isdigit() or len(mesh_code) != 8:
        return {
            "success": False,
            "building": None,
            "mesh_code": mesh_code,
            "citygml_xml": None,
            "total_buildings_in_mesh": None,
            "error": "Invalid mesh code format",
            "error_details": f"Expected 8-digit number, got: {mesh_code}"
        }

    # Step 2: Validate building ID format (accept both building ID and GML ID)
    # GML ID format: bldg_uuid (e.g., bldg_48aa415d-b82f-4e8f-97e1-7538b5cb6c86)
    # Building ID format: 13101-bldg-2287 (legacy, rarely exists in actual data)
    if not building_id or not (building_id.startswith("bldg_") or "-bldg-" in building_id):
        return {
            "success": False,
            "building": None,
            "mesh_code": mesh_code,
            "citygml_xml": None,
            "total_buildings_in_mesh": None,
            "error": "Invalid building ID format",
            "error_details": f"Expected GML ID (bldg_...) or building ID (xxxxx-bldg-nnn), got: {building_id}"
        }

    # Step 3: Fetch CityGML for the specified mesh code
    xml_content = fetch_citygml_by_mesh_code(mesh_code)
    if not xml_content:
        return {
            "success": False,
            "building": None,
            "mesh_code": mesh_code,
            "citygml_xml": None,
            "total_buildings_in_mesh": None,
            "error": "Failed to fetch PLATEAU data",
            "error_details": f"No CityGML data found for mesh code: {mesh_code}"
        }

    # Step 4: Parse buildings
    buildings = parse_buildings_from_citygml(xml_content)
    if not buildings:
        return {
            "success": False,
            "building": None,
            "mesh_code": mesh_code,
            "citygml_xml": xml_content,
            "total_buildings_in_mesh": 0,
            "error": "No buildings found in mesh area",
            "error_details": f"Mesh code {mesh_code} contains no parseable buildings"
        }

    total_buildings = len(buildings)
    print(f"[BUILDING SEARCH] Found {total_buildings} building(s) in mesh {mesh_code}")

    # Debug: Show sample of extracted building IDs
    print(f"[BUILDING SEARCH] Searching for building_id: '{building_id}'")
    print(f"[BUILDING SEARCH] Sample building IDs from mesh (first 5):")
    for i, b in enumerate(buildings[:5], 1):
        print(f"[BUILDING SEARCH]   {i}. gml_id: {b.gml_id}")
        print(f"[BUILDING SEARCH]      building_id: {b.building_id or 'None'}")

    # Step 5: Find building by ID (exact match on gml_id or building_id)
    target_building = None
    for building in buildings:
        if building.gml_id == building_id or (building.building_id and building.building_id == building_id):
            target_building = building
            print(f"[BUILDING SEARCH] ✓ Match found: {building.building_id or building.gml_id}")
            break

    # Fallback: Try fuzzy match (case-insensitive, strip whitespace)
    if not target_building:
        building_id_normalized = building_id.strip().lower()
        for building in buildings:
            gml_id_normalized = building.gml_id.strip().lower() if building.gml_id else ""
            building_id_norm = building.building_id.strip().lower() if building.building_id else ""

            if gml_id_normalized == building_id_normalized or building_id_norm == building_id_normalized:
                target_building = building
                break

    if not target_building:
        # Collect similar IDs for error message (show both gml_id and building_id)
        similar_ids = []
        for b in buildings[:5]:
            if b.building_id:
                similar_ids.append(f"{b.building_id} (gml:{b.gml_id[:30]}...)")
            else:
                similar_ids.append(f"gml:{b.gml_id[:50]}")

        print(f"[BUILDING SEARCH] ❌ Building not found!")
        print(f"[BUILDING SEARCH] Searched: '{building_id}'")
        print(f"[BUILDING SEARCH] Example IDs: {similar_ids[:3]}")

        return {
            "success": False,
            "building": None,
            "mesh_code": mesh_code,
            "citygml_xml": xml_content,
            "total_buildings_in_mesh": total_buildings,
            "error": "Building not found in mesh area",
            "error_details": f"Searched {total_buildings} buildings in mesh {mesh_code}, but building ID '{building_id}' was not found. Example IDs from this area: {', '.join(similar_ids[:3])}"
        }

    print(f"\n{'='*60}")
    print(f"[BUILDING SEARCH] Success: Found building!")
    print(f"[BUILDING SEARCH]   ID: {target_building.gml_id}")
    print(f"[BUILDING SEARCH]   Name: {target_building.name or 'N/A'}")
    print(f"[BUILDING SEARCH]   Height: {target_building.height or target_building.measured_height or 'N/A'}m")
    print(f"[BUILDING SEARCH]   LOD2: {target_building.has_lod2}, LOD3: {target_building.has_lod3}")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "building": target_building,
        "mesh_code": mesh_code,
        "citygml_xml": xml_content,
        "total_buildings_in_mesh": total_buildings,
        "error": None,
        "error_details": None
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
