"""
Coordinate system utilities for CityGML conversion.

This module provides utilities for detecting coordinate reference systems (CRS)
and automatically selecting appropriate projected coordinate systems for
geographic coordinates, with special support for Japanese PLATEAU data.
"""

from typing import Optional, Tuple, Dict
import re
import math


# Japan Plane Rectangular Coordinate Systems (JGD2011)
# Mapping from zone number to EPSG code and approximate coverage area
JAPAN_PLANE_ZONES: Dict[int, Dict] = {
    1: {
        "epsg": "EPSG:6669",
        "name": "JGD2011 / Japan Plane Rectangular CS I",
        "lat_range": (33.0, 34.5),
        "lon_range": (129.3, 130.7),
        "regions": ["長崎県", "鹿児島県の一部"]
    },
    2: {
        "epsg": "EPSG:6670", 
        "name": "JGD2011 / Japan Plane Rectangular CS II",
        "lat_range": (32.0, 34.0),
        "lon_range": (130.0, 131.5),
        "regions": ["福岡県", "佐賀県", "熊本県", "大分県", "宮崎県", "鹿児島県の一部"]
    },
    3: {
        "epsg": "EPSG:6671",
        "name": "JGD2011 / Japan Plane Rectangular CS III", 
        "lat_range": (35.5, 36.5),
        "lon_range": (131.5, 133.0),
        "regions": ["山口県", "島根県", "広島県"]
    },
    4: {
        "epsg": "EPSG:6672",
        "name": "JGD2011 / Japan Plane Rectangular CS IV",
        "lat_range": (34.5, 35.5),
        "lon_range": (132.5, 134.5),
        "regions": ["香川県", "愛媛県", "徳島県", "高知県"]
    },
    5: {
        "epsg": "EPSG:6673",
        "name": "JGD2011 / Japan Plane Rectangular CS V",
        "lat_range": (35.5, 36.5),
        "lon_range": (133.5, 135.5),
        "regions": ["兵庫県", "鳥取県", "岡山県"]
    },
    6: {
        "epsg": "EPSG:6674",
        "name": "JGD2011 / Japan Plane Rectangular CS VI",
        "lat_range": (35.0, 36.5),
        "lon_range": (135.0, 137.0),
        "regions": ["京都府", "大阪府", "福井県", "滋賀県", "三重県", "奈良県", "和歌山県"]
    },
    7: {
        "epsg": "EPSG:6675",
        "name": "JGD2011 / Japan Plane Rectangular CS VII",
        "lat_range": (35.5, 37.0),
        "lon_range": (136.5, 138.0),
        "regions": ["石川県", "富山県", "岐阜県", "愛知県"]
    },
    8: {
        "epsg": "EPSG:6676",
        "name": "JGD2011 / Japan Plane Rectangular CS VIII",
        "lat_range": (35.5, 36.5),
        "lon_range": (137.5, 139.5),
        "regions": ["新潟県", "長野県", "山梨県", "静岡県"]
    },
    9: {
        "epsg": "EPSG:6677",
        "name": "JGD2011 / Japan Plane Rectangular CS IX",
        "lat_range": (35.0, 36.5),
        "lon_range": (139.0, 140.5),
        "regions": ["東京都", "福島県", "栃木県", "茨城県", "埼玉県", "千葉県", "群馬県", "神奈川県"]
    },
    10: {
        "epsg": "EPSG:6678",
        "name": "JGD2011 / Japan Plane Rectangular CS X",
        "lat_range": (39.5, 41.0),
        "lon_range": (139.5, 141.0),
        "regions": ["青森県", "秋田県", "山形県", "岩手県", "宮城県"]
    },
    11: {
        "epsg": "EPSG:6679",
        "name": "JGD2011 / Japan Plane Rectangular CS XI",
        "lat_range": (41.5, 43.0),
        "lon_range": (139.5, 141.0),
        "regions": ["北海道の一部", "青森県の一部"]
    },
    12: {
        "epsg": "EPSG:6680",
        "name": "JGD2011 / Japan Plane Rectangular CS XII",
        "lat_range": (43.0, 44.5),
        "lon_range": (141.0, 143.0),
        "regions": ["北海道の一部"]
    },
    13: {
        "epsg": "EPSG:6681",
        "name": "JGD2011 / Japan Plane Rectangular CS XIII",
        "lat_range": (43.5, 45.0),
        "lon_range": (142.0, 145.0),
        "regions": ["北海道の一部"]
    },
    14: {
        "epsg": "EPSG:6682",
        "name": "JGD2011 / Japan Plane Rectangular CS XIV",
        "lat_range": (25.5, 27.0),
        "lon_range": (126.5, 128.0),
        "regions": ["沖縄県の一部"]
    },
    15: {
        "epsg": "EPSG:6683",
        "name": "JGD2011 / Japan Plane Rectangular CS XV",
        "lat_range": (25.5, 26.5),
        "lon_range": (123.5, 125.0),
        "regions": ["沖縄県の一部"]
    },
    16: {
        "epsg": "EPSG:6684",
        "name": "JGD2011 / Japan Plane Rectangular CS XVI",
        "lat_range": (25.5, 26.5),
        "lon_range": (123.5, 125.0),
        "regions": ["沖縄県の一部"]
    },
    17: {
        "epsg": "EPSG:6685",
        "name": "JGD2011 / Japan Plane Rectangular CS XVII",
        "lat_range": (25.5, 26.5),
        "lon_range": (130.5, 132.0),
        "regions": ["沖縄県の一部"]
    },
    18: {
        "epsg": "EPSG:6686",
        "name": "JGD2011 / Japan Plane Rectangular CS XVIII",
        "lat_range": (19.5, 21.0),
        "lon_range": (135.5, 137.0),
        "regions": ["東京都（小笠原）"]
    },
    19: {
        "epsg": "EPSG:6687",
        "name": "JGD2011 / Japan Plane Rectangular CS XIX",
        "lat_range": (24.0, 28.0),
        "lon_range": (152.5, 154.5),
        "regions": ["東京都（南鳥島）"]
    }
}


def detect_epsg_from_srs(srs: str) -> Optional[str]:
    """
    Extract EPSG code from an srsName string.
    
    Args:
        srs: srsName attribute value (e.g., 'http://www.opengis.net/def/crs/EPSG/0/6697')
    
    Returns:
        EPSG code string (e.g., 'EPSG:6697') or None if not found
    """
    if not srs:
        return None
    
    # Handle URLs like http://www.opengis.net/def/crs/EPSG/0/6697
    m = re.search(r"EPSG[/:#\s]+\d+[/:#\s]+(\d+)", srs, re.IGNORECASE)
    if m:
        return f"EPSG:{m.group(1)}"
    
    # Fallback to simpler pattern
    m = re.search(r"EPSG[/:#\s]+(\d+)", srs, re.IGNORECASE)
    if m:
        return f"EPSG:{m.group(1)}"
    
    return None


def is_geographic_crs(epsg_code: str) -> bool:
    """
    Check if an EPSG code represents a geographic (lat/lon) coordinate system.
    
    Args:
        epsg_code: EPSG code string (e.g., 'EPSG:6697')
    
    Returns:
        True if geographic CRS, False otherwise
    """
    # Common geographic CRS codes used in Japan/PLATEAU
    geographic_codes = [
        "4326",  # WGS84
        "4612",  # JGD2000
        "6668",  # JGD2011
        "6697",  # JGD2011 / (vertical) / height
        "4019",  # GRS 1980
    ]
    
    if not epsg_code:
        return False
    
    # Extract numeric part
    code_num = epsg_code.replace("EPSG:", "").replace("epsg:", "")
    return code_num in geographic_codes


def get_japan_plane_zone(lat: float, lon: float) -> Optional[str]:
    """
    Determine the appropriate Japan Plane Rectangular CS zone for given coordinates.
    
    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
    
    Returns:
        EPSG code for the appropriate zone or None if outside Japan
    """
    # Quick check if coordinates are in Japan's general area
    if not (20 <= lat <= 46 and 122 <= lon <= 154):
        return None
    
    # Find the best matching zone
    best_zone = None
    best_distance = float('inf')
    
    for zone_num, zone_info in JAPAN_PLANE_ZONES.items():
        lat_min, lat_max = zone_info["lat_range"]
        lon_min, lon_max = zone_info["lon_range"]
        
        # Check if point is within zone bounds
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            # Calculate distance to zone center for tie-breaking
            lat_center = (lat_min + lat_max) / 2
            lon_center = (lon_min + lon_max) / 2
            distance = math.sqrt((lat - lat_center)**2 + (lon - lon_center)**2)
            
            if distance < best_distance:
                best_distance = distance
                best_zone = zone_info["epsg"]
    
    # If no exact match, use zone 9 (Tokyo area) as default for central Japan
    if best_zone is None and 34 <= lat <= 37 and 138 <= lon <= 141:
        best_zone = "EPSG:6677"  # Zone IX - Tokyo area
    
    return best_zone


def recommend_projected_crs(source_crs: str, sample_lat: Optional[float] = None, 
                           sample_lon: Optional[float] = None) -> Optional[str]:
    """
    Recommend an appropriate projected CRS for a given geographic CRS.
    
    Args:
        source_crs: Source EPSG code (e.g., 'EPSG:6697')
        sample_lat: Sample latitude from the data (optional)
        sample_lon: Sample longitude from the data (optional)
    
    Returns:
        Recommended projected CRS EPSG code or None
    """
    if not is_geographic_crs(source_crs):
        # Already projected, no conversion needed
        return None
    
    # If we have sample coordinates, try to determine Japan plane zone
    if sample_lat is not None and sample_lon is not None:
        japan_zone = get_japan_plane_zone(sample_lat, sample_lon)
        if japan_zone:
            return japan_zone
    
    # Default recommendations based on source CRS
    if source_crs in ["EPSG:6697", "EPSG:6668", "EPSG:4612"]:
        # Japanese geographic CRS - default to Tokyo area (Zone IX)
        return "EPSG:6677"
    elif source_crs == "EPSG:4326":
        # WGS84 - need sample coordinates to determine zone
        if sample_lat and sample_lon:
            return get_japan_plane_zone(sample_lat, sample_lon)
        # Default to Web Mercator if no coordinates available
        return "EPSG:3857"
    
    return None


def get_crs_info(epsg_code: str) -> Dict[str, str]:
    """
    Get human-readable information about a CRS.
    
    Args:
        epsg_code: EPSG code string
    
    Returns:
        Dictionary with CRS information
    """
    # Extract zone number if it's a Japan Plane CS
    if epsg_code.startswith("EPSG:"):
        code_num = epsg_code.replace("EPSG:", "")
        for zone_num, zone_info in JAPAN_PLANE_ZONES.items():
            if zone_info["epsg"] == epsg_code:
                return {
                    "code": epsg_code,
                    "name": zone_info["name"],
                    "regions": ", ".join(zone_info["regions"]),
                    "type": "projected"
                }
    
    # Common CRS names
    known_crs = {
        "EPSG:6697": {"name": "JGD2011 / (vertical) / height", "type": "geographic"},
        "EPSG:6668": {"name": "JGD2011", "type": "geographic"},
        "EPSG:4612": {"name": "JGD2000", "type": "geographic"},
        "EPSG:4326": {"name": "WGS 84", "type": "geographic"},
        "EPSG:3857": {"name": "WGS 84 / Pseudo-Mercator", "type": "projected"},
    }
    
    if epsg_code in known_crs:
        return {
            "code": epsg_code,
            "name": known_crs[epsg_code]["name"],
            "type": known_crs[epsg_code]["type"]
        }
    
    return {
        "code": epsg_code,
        "name": "Unknown CRS",
        "type": "unknown"
    }