"""
Constants for CityGML to STEP conversion.

This module defines all constant values used throughout the conversion pipeline,
including XML namespaces, tolerance multipliers, thresholds, and configuration
parameters.
"""

# ============================================================================
# XML Namespaces (CityGML 2.0 / PLATEAU)
# ============================================================================

NS = {
    "gml": "http://www.opengis.net/gml",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "core": "http://www.opengis.net/citygml/2.0",
    "uro": "https://www.geospatial.jp/iur/uro/3.1",  # PLATEAU-specific namespace (iur/uro 3.1)
    "gen": "http://www.opengis.net/citygml/generics/2.0",
    "xlink": "http://www.w3.org/1999/xlink",
}

# ============================================================================
# Tolerance Configuration
# ============================================================================

# Precision mode to tolerance factor mapping
# tolerance = extent * PRECISION_MODE_FACTORS[precision_mode]
PRECISION_MODE_FACTORS = {
    "standard": 0.0001,    # 0.01% of extent (balanced, default)
    "high": 0.00001,       # 0.001% of extent (preserves fine details)
    "maximum": 0.000001,   # 0.0001% of extent (maximum detail preservation)
    "ultra": 0.0000001,    # 0.00001% of extent (LOD2/LOD3 optimized)
}

# Progressive tolerance escalation multipliers for ultra mode sewing
# Applied in sequence: tolerance * 10.0 → tolerance * 5.0 → tolerance
# ⚠️ CRITICAL: Do not change these values without thorough testing
ULTRA_MODE_TOLERANCE_MULTIPLIERS = [10.0, 5.0, 1.0]

# Maximum tolerance multiplier for shape fixing (ultra mode)
# max_tolerance = tolerance * MAX_TOLERANCE_MULTIPLIER
MAX_TOLERANCE_MULTIPLIER = 1000.0

# ============================================================================
# Coordinate Recentering (PHASE:0)
# ============================================================================

# Minimum distance from origin (meters) to trigger coordinate recentering
# If bounding box center is farther than this, coordinates are recentered
# to prevent OpenCASCADE precision loss
# ⚠️ CRITICAL: Must be applied BEFORE tolerance calculation
RECENTERING_DISTANCE_THRESHOLD = 1.0  # meters

# ============================================================================
# Shell Validation Thresholds
# ============================================================================

# Maximum acceptable ratio of invalid faces in a shell
# If a shell has more than this percentage of invalid faces, it is rejected
# Default: 5% (0.05)
INVALID_FACE_RATIO_THRESHOLD = 0.05

# ============================================================================
# Issue #48: LOD2 boundedBy Comparison
# ============================================================================

# Threshold for preferring boundedBy over lod2Solid
# If bounded_faces_count >= lod2Solid_faces * threshold, prefer boundedBy
# ⚠️ CRITICAL: Fixed threshold of 1.0 (changed from 1.2 to fix wall omission)
# See issue #48 for details
BOUNDED_BY_PREFERENCE_THRESHOLD = 1.0

# ============================================================================
# Auto-Escalation Level Map
# ============================================================================

# Shape fix level escalation paths for auto-repair
# Each level defines which escalation levels to try in sequence
# ⚠️ CRITICAL: Preserve exact escalation paths
AUTO_ESCALATION_MAP = {
    'minimal': ['minimal', 'standard', 'aggressive', 'ultra'],
    'standard': ['standard', 'aggressive', 'ultra'],
    'aggressive': ['aggressive', 'ultra'],
    'ultra': ['ultra']
}

# ============================================================================
# BoundarySurface Types (CityGML 2.0)
# ============================================================================

# All 6 CityGML 2.0 boundary surface types
BOUNDARY_SURFACE_TYPES = [
    'WallSurface',
    'RoofSurface',
    'GroundSurface',
    'OuterCeilingSurface',
    'OuterFloorSurface',
    'ClosureSurface',
]

# ============================================================================
# LOD Levels
# ============================================================================

# LOD priority order (highest to lowest detail)
# ⚠️ CRITICAL: Must be preserved in this exact order
LOD_PRIORITY = ['LOD3', 'LOD2', 'LOD1']

# LOD level to tag name mapping
LOD_SOLID_TAGS = {
    'LOD3': 'lod3Solid',
    'LOD2': 'lod2Solid',
    'LOD1': 'lod1Solid',
}

LOD_MULTISURFACE_TAGS = {
    'LOD3': 'lod3MultiSurface',
    'LOD2': 'lod2MultiSurface',
}

LOD_GEOMETRY_TAGS = {
    'LOD3': 'lod3Geometry',
    'LOD2': 'lod2Geometry',
}

# ============================================================================
# Default Values
# ============================================================================

DEFAULT_BUILDING_HEIGHT = 10.0  # meters (used for footprint extrusion if height unavailable)
DEFAULT_COORDINATE_FILTER_RADIUS = 100.0  # meters (for coordinate-based building filtering)

# ============================================================================
# Validation Constants
# ============================================================================

# Minimum number of points for a valid polygon
MIN_POLYGON_POINTS = 3

# Minimum wire length to be considered valid (meters)
MIN_WIRE_LENGTH = 1e-6
