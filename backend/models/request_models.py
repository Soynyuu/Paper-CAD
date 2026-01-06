from pydantic import BaseModel, Field
from typing import Optional

class BrepPapercraftRequest(BaseModel):
    """STEP to SVG/PDF unfold request parameters (STEP → 展開図変換リクエストパラメータ)"""

    scale_factor: float = Field(
        default=10.0,
        description="図の縮尺倍率 (例: 150なら1/150スケール) / Scale factor (e.g., 150 = 1:150 scale)",
        gt=0,
        example=150.0
    )
    units: str = Field(
        default="mm",
        description="単位 / Units (mm/cm/m)",
        pattern="^(mm|cm|m)$",
        example="mm"
    )
    max_faces: int = Field(
        default=20,
        description="1グループあたりの最大面数 / Maximum faces per group",
        ge=1,
        le=100,
        example=20
    )
    curvature_tolerance: float = Field(
        default=0.1,
        description="曲率許容誤差 / Curvature tolerance",
        gt=0,
        example=0.1
    )
    tab_width: float = Field(
        default=5.0,
        description="接着タブの幅 (mm) / Tab width for assembly (mm)",
        ge=0,
        example=5.0
    )
    min_face_area: float = Field(
        default=1.0,
        description="最小面積フィルタ (mm²) - この値未満の面は除外 / Minimum face area filter (mm²)",
        ge=0,
        example=1.0
    )
    unfold_method: str = Field(
        default="planar",
        description="展開アルゴリズム / Unfold algorithm (planar/geodesic)",
        pattern="^(planar|geodesic)$",
        example="planar"
    )
    show_scale: bool = Field(
        default=True,
        description="縮尺バーを表示 / Show scale bar",
        example=True
    )
    show_fold_lines: bool = Field(
        default=True,
        description="折り線を表示 / Show fold lines",
        example=True
    )
    show_cut_lines: bool = Field(
        default=True,
        description="切り線を表示 / Show cut lines",
        example=True
    )
    layout_mode: str = Field(
        default="paged",
        description="レイアウトモード / Layout mode (canvas=フリーキャンバス, paged=ページ分割)",
        pattern="^(canvas|paged)$",
        example="paged"
    )
    page_format: str = Field(
        default="A4",
        description="ページフォーマット / Page format (A4/A3/Letter)",
        pattern="^(A4|A3|Letter)$",
        example="A4"
    )
    page_orientation: str = Field(
        default="portrait",
        description="ページ向き / Page orientation (portrait=縦, landscape=横)",
        pattern="^(portrait|landscape)$",
        example="portrait"
    )
    mirror_horizontal: bool = Field(
        default=False,
        description="左右反転モード / Mirror horizontally",
        example=False
    )


class PlateauSearchRequest(BaseModel):
    """Request to search for PLATEAU buildings by address/facility name (住所・施設名でPLATEAU建物検索)"""

    query: str = Field(
        description="住所または施設名 / Address or facility name (例: '東京駅', '渋谷スクランブルスクエア')",
        min_length=1,
        example="東京駅"
    )
    radius: Optional[float] = Field(
        default=0.001,
        description="検索半径（度単位、約100m） / Search radius in degrees (~100m)",
        gt=0,
        example=0.001
    )
    limit: Optional[int] = Field(
        default=10,
        description="最大検索結果数 / Maximum number of results",
        ge=1,
        le=100,
        example=10
    )
    auto_select_nearest: Optional[bool] = Field(
        default=True,
        description="最近接建物を自動選択 / Auto-select nearest building",
        example=True
    )
    name_filter: Optional[str] = Field(
        default=None,
        description="建物名フィルタ（名前ベース検索用） / Building name filter for ranking",
        example=None
    )
    search_mode: Optional[str] = Field(
        default="hybrid",
        description="検索モード / Search mode (distance/name/hybrid)",
        pattern="^(distance|name|hybrid)$",
        example="hybrid"
    )


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


class PlateauBuildingIdRequest(BaseModel):
    """Request to fetch PLATEAU building by building ID (建物IDでPLATEAU建物を取得)"""

    building_id: str = Field(
        description="建物ID / Building ID (例: '13101-bldg-2287')",
        min_length=1,
        example="13101-bldg-2287"
    )
    merge_building_parts: Optional[bool] = Field(
        default=False,
        description="BuildingPartを結合 / Merge BuildingPart into main building",
        example=False
    )
    precision_mode: Optional[str] = Field(
        default="ultra",
        description="精度モード / Precision mode (standard/high/maximum/ultra)",
        pattern="^(standard|high|maximum|ultra)$",
        example="ultra"
    )
    shape_fix_level: Optional[str] = Field(
        default="minimal",
        description="形状修正レベル / Shape fixing level (minimal/standard/aggressive/ultra)",
        pattern="^(minimal|standard|aggressive|ultra)$",
        example="minimal"
    )
    method: Optional[str] = Field(
        default="solid",
        description="変換方法 / Conversion method (solid/sew/extrude/auto)",
        pattern="^(solid|sew|extrude|auto)$",
        example="solid"
    )
    auto_reproject: Optional[bool] = Field(
        default=True,
        description="平面直角座標系へ自動変換 / Auto-reproject to planar CRS",
        example=True
    )
    debug: Optional[bool] = Field(
        default=False,
        description="デバッグモード / Debug mode",
        example=False
    )


class PlateauBuildingIdWithMeshRequest(BaseModel):
    """Request to fetch PLATEAU building by building ID + mesh code (optimized) (建物ID+メッシュコードで取得、最適化版)"""

    building_id: str = Field(
        description="建物ID / Building ID (例: '13101-bldg-2287')",
        min_length=1,
        example="13101-bldg-2287"
    )
    mesh_code: str = Field(
        description="3次メッシュコード（8桁、1km区画） / 3rd mesh code (8 digits, 1km area, 例: '53394511')",
        pattern="^[0-9]{8}$",
        example="53394511"
    )
    merge_building_parts: Optional[bool] = Field(
        default=False,
        description="BuildingPartを結合 / Merge BuildingPart into main building",
        example=False
    )
    precision_mode: Optional[str] = Field(
        default="ultra",
        description="精度モード / Precision mode (standard/high/maximum/ultra)",
        pattern="^(standard|high|maximum|ultra)$",
        example="ultra"
    )
    shape_fix_level: Optional[str] = Field(
        default="minimal",
        description="形状修正レベル / Shape fixing level (minimal/standard/aggressive/ultra)",
        pattern="^(minimal|standard|aggressive|ultra)$",
        example="minimal"
    )
    method: Optional[str] = Field(
        default="solid",
        description="変換方法 / Conversion method (solid/sew/extrude/auto)",
        pattern="^(solid|sew|extrude|auto)$",
        example="solid"
    )
    auto_reproject: Optional[bool] = Field(
        default=True,
        description="平面直角座標系へ自動変換 / Auto-reproject to planar CRS",
        example=True
    )
    debug: Optional[bool] = Field(
        default=False,
        description="デバッグモード / Debug mode",
        example=False
    )


class PlateauBuildingIdSearchResponse(BaseModel):
    """Response from building ID search"""
    success: bool
    building: Optional[BuildingInfoResponse] = None
    municipality_code: Optional[str] = None  # Extracted municipality code
    municipality_name: Optional[str] = None  # Municipality name (if found)
    citygml_file: Optional[str] = None  # CityGML file name
    total_buildings_in_file: Optional[int] = None  # Total buildings found in CityGML
    error: Optional[str] = None
    error_details: Optional[str] = None  # Detailed error information


class BuildingIdWithMeshItem(BaseModel):
    """Single building ID + mesh code item for batch request (Phase 6.1)"""
    building_id: str = Field(
        description="建物ID / Building ID (例: '13101-bldg-2287')",
        min_length=1,
        example="13101-bldg-2287"
    )
    mesh_code: str = Field(
        description="3次メッシュコード（8桁、1km区画） / 3rd mesh code (8 digits, 1km area, 例: '53394511')",
        pattern="^[0-9]{8}$",
        example="53394511"
    )


class PlateauBatchBuildingRequest(BaseModel):
    """Request for batch building search (Phase 6.1)"""
    buildings: list[BuildingIdWithMeshItem] = Field(
        description="建物ID+メッシュコードのリスト / List of building ID + mesh code pairs",
        min_length=1,
        max_length=100,  # Limit to 100 buildings per batch
        example=[
            {"building_id": "13101-bldg-2287", "mesh_code": "53394511"},
            {"building_id": "13101-bldg-2288", "mesh_code": "53394511"}
        ]
    )


class PlateauBatchBuildingResponse(BaseModel):
    """Response for batch building search (Phase 6.1)"""
    results: list[PlateauBuildingIdSearchResponse] = Field(
        description="検索結果のリスト（各建物の検索レスポンス） / List of search results for each building"
    )
    total_requested: int = Field(
        description="リクエストした建物の総数 / Total number of buildings requested"
    )
    total_success: int = Field(
        description="正常に取得できた建物数 / Number of successfully retrieved buildings"
    )
    total_failed: int = Field(
        description="取得失敗した建物数 / Number of failed retrievals"
    )