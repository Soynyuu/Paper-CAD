from pydantic import BaseModel
from typing import Optional

class BrepPapercraftRequest(BaseModel):
    scale_factor: float = 10.0  # デフォルトスケールファクターを大きくする
    units: str = "mm" #単位形の指定
    max_faces: int = 20
    curvature_tolerance: float = 0.1
    # ═══ 接着工学：物理的組み立ての実践的考慮 ═══
    tab_width: float = 5.0
    # ═══ 品質フィルタリング：微細要素の除外戦略 ═══
    min_face_area: float = 1.0
        # ═══ 展開アルゴリズム選択：数学的手法の戦略的選択 ═══
    unfold_method: str = "planar"
    # ═══ 視覚化制御：図面の情報密度管理 ═══
    show_scale: bool = True
    show_fold_lines: bool = True
    show_cut_lines: bool = True
    # ═══ レイアウトオプション：出力形式の制御 ═══
    layout_mode: str = "paged"  # "canvas" (フリーキャンバス) or "paged" (ページ分割)
    page_format: str = "A4"  # ページフォーマット: A4, A3, Letter
    page_orientation: str = "portrait"  # ページ向き: portrait (縦) or landscape (横)


class CityGMLConversionRequest(BaseModel):
    """CityGML to STEP conversion request parameters"""
    # Parsing options
    preferred_lod: Optional[int] = 2  # Preferred Level of Detail (0, 1, 2)
    min_building_area: Optional[float] = None  # Minimum building area to process (square meters)
    max_building_count: Optional[int] = None  # Maximum number of buildings to process

    # Building filtering options
    building_ids: Optional[list[str]] = None  # List of building IDs to extract (None = all buildings)
    filter_attribute: Optional[str] = "gml:id"  # Attribute to match building_ids against (default: gml:id)

    # Solidification options
    tolerance: Optional[float] = 1e-6  # Geometric tolerance for solid creation
    enable_shell_closure: Optional[bool] = True  # Attempt to close open shells

    # Export options
    export_individual_files: Optional[bool] = False  # Export each building as separate STEP file
    output_format: Optional[str] = "step"  # Output format (currently only STEP supported)

    # Processing options
    debug_mode: Optional[bool] = False  # Enable debug logging and detailed error reporting


class CityGMLValidationRequest(BaseModel):
    """CityGML file validation request parameters"""
    check_geometry: Optional[bool] = True  # Validate geometric structure
    estimate_processing_time: Optional[bool] = True  # Provide processing time estimates


class PlateauSearchRequest(BaseModel):
    """Request to search for PLATEAU buildings by address/facility name"""
    query: str  # Address or facility name (e.g., "東京駅", "東京都千代田区丸の内1-9-1")
    radius: Optional[float] = 0.001  # Search radius in degrees (default: ~100m)
    limit: Optional[int] = 10  # Maximum number of buildings to return
    auto_select_nearest: Optional[bool] = True  # Auto-select nearest building
    name_filter: Optional[str] = None  # Building name to filter/rank by (for name-based search)
    search_mode: Optional[str] = "hybrid"  # Ranking strategy: "distance", "name", or "hybrid"


class PlateauFetchAndConvertRequest(BaseModel):
    """Request to fetch PLATEAU data and convert to STEP in one step"""
    query: str  # Address or facility name
    radius: Optional[float] = 0.001  # Search radius in degrees
    auto_select_nearest: Optional[bool] = True  # Auto-select nearest building
    building_limit: Optional[int] = 1  # Number of buildings to convert
    building_ids: Optional[list[str]] = None  # Specific building IDs to convert (user selection)
    # Conversion options (reuse existing CityGML conversion parameters)
    debug: Optional[bool] = False
    method: Optional[str] = "solid"
    auto_reproject: Optional[bool] = True
    precision_mode: Optional[str] = "ultra"
    shape_fix_level: Optional[str] = "ultra"


class BuildingInfoResponse(BaseModel):
    """Information about a single building from PLATEAU"""
    building_id: Optional[str]  # Stable building ID (e.g., "13101-bldg-123456")
    gml_id: str  # Technical GML identifier
    latitude: float
    longitude: float
    distance_meters: float
    height: Optional[float] = None
    usage: Optional[str] = None
    measured_height: Optional[float] = None
    name: Optional[str] = None  # Building name from CityGML
    relevance_score: Optional[float] = None  # Composite relevance score (0.0-1.0)
    name_similarity: Optional[float] = None  # Name matching score (0.0-1.0)
    match_reason: Optional[str] = None  # Explanation of why this building matched
    has_lod2: bool = False  # Does the building have LOD2 geometry?
    has_lod3: bool = False  # Does the building have LOD3 geometry?


class GeocodingResultResponse(BaseModel):
    """Geocoding result information"""
    query: str
    latitude: float
    longitude: float
    display_name: str
    osm_type: Optional[str] = None
    osm_id: Optional[int] = None


class PlateauSearchResponse(BaseModel):
    """Response from building search"""
    success: bool
    geocoding: Optional[GeocodingResultResponse]
    buildings: list[BuildingInfoResponse]
    found_count: int
    search_mode: Optional[str] = "hybrid"  # The search mode that was used
    error: Optional[str] = None