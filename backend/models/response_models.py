from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class HealthCheckResponse(BaseModel):
    """Health check response (ヘルスチェックレスポンス)"""

    status: str = Field(
        description="ステータス / Status (healthy/degraded)",
        example="healthy"
    )
    opencascade_available: bool = Field(
        description="OpenCASCADE の利用可否 / OCCT availability",
        example=True
    )
    supported_formats: List[str] = Field(
        description="サポートされるファイル形式 / Supported file formats",
        example=["STEP", "BREP", "CityGML", "PLATEAU"]
    )
    features: Dict[str, bool] = Field(
        description="有効な機能フラグ / Enabled feature flags",
        example={
            "step_unfold": True,
            "citygml_conversion": True,
            "plateau_integration": True,
            "pdf_export": True
        }
    )


class CityGMLValidationResponse(BaseModel):
    """CityGML validation response (CityGML検証レスポンス)"""

    valid: bool = Field(
        description="検証結果 / Validation result",
        example=True
    )
    building_count: int = Field(
        description="建物数 / Number of buildings",
        example=42
    )
    building_ids: List[str] = Field(
        description="建物IDリスト（サンプル） / Building IDs (sample)",
        example=["bldg_001", "bldg_002", "bldg_003"]
    )
    has_lod1: bool = Field(
        default=False,
        description="LOD1データの有無 / Has LOD1 data",
        example=False
    )
    has_lod2: bool = Field(
        default=False,
        description="LOD2データの有無 / Has LOD2 data",
        example=True
    )
    has_lod3: bool = Field(
        default=False,
        description="LOD3データの有無 / Has LOD3 data",
        example=False
    )
    coordinate_system: Optional[str] = Field(
        default=None,
        description="座標系 / Coordinate system (CRS)",
        example="EPSG:6677"
    )
    warnings: List[str] = Field(
        default=[],
        description="警告メッセージ / Warning messages",
        example=[]
    )
    errors: List[str] = Field(
        default=[],
        description="エラーメッセージ / Error messages",
        example=[]
    )


class UnfoldStatsResponse(BaseModel):
    """Unfold statistics (展開統計情報)"""

    total_faces: int = Field(
        description="総面数 / Total number of faces",
        example=42
    )
    page_count: Optional[int] = Field(
        default=None,
        description="ページ数 / Number of pages (paged mode only)",
        example=3
    )
    layout_mode: str = Field(
        description="レイアウトモード / Layout mode",
        example="paged"
    )
    page_format: Optional[str] = Field(
        default=None,
        description="ページフォーマット / Page format",
        example="A4"
    )
    scale_factor: float = Field(
        description="縮尺倍率 / Scale factor",
        example=150.0
    )


class UnfoldResponse(BaseModel):
    """STEP unfold response (STEP展開レスポンス)"""

    success: bool = Field(
        description="成功フラグ / Success flag",
        example=True
    )
    svg_content: Optional[str] = Field(
        default=None,
        description="SVGコンテンツ / SVG content (if JSON response)",
        example="<svg>...</svg>"
    )
    stats: Optional[UnfoldStatsResponse] = Field(
        default=None,
        description="統計情報 / Statistics",
        example=None
    )
    face_numbers: Optional[List[int]] = Field(
        default=None,
        description="面番号リスト / Face numbers",
        example=[1, 2, 3, 4, 5]
    )
    error: Optional[str] = Field(
        default=None,
        description="エラーメッセージ / Error message",
        example=None
    )
