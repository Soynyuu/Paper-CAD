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
    layout_mode: str = "canvas"  # "canvas" (フリーキャンバス) or "paged" (ページ分割)
    page_format: str = "A4"  # ページフォーマット: A4, A3, Letter
    page_orientation: str = "portrait"  # ページ向き: portrait (縦) or landscape (横)


class CityGMLConversionRequest(BaseModel):
    """CityGML to STEP conversion request parameters"""
    # Parsing options
    preferred_lod: Optional[int] = 2  # Preferred Level of Detail (0, 1, 2)
    min_building_area: Optional[float] = None  # Minimum building area to process (square meters)
    max_building_count: Optional[int] = None  # Maximum number of buildings to process
    
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