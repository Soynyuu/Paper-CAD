import os
import tempfile
from typing import Optional, Union

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from api.helpers import cleanup_temp_dir, normalize_limit_param, parse_csv_ids, save_upload_to_tmpdir
from services.citygml import export_step_from_citygml
from services.citygml.lod.footprint_extractor import parse_citygml_footprints

router = APIRouter()


# --- CityGML → STEP 変換エンドポイント ---
@router.post(
    "/api/citygml/to-step",
    summary="CityGML → STEP Conversion",
    tags=["CityGML Processing"],
    responses={
        200: {
            "description": "STEP file generated successfully with LOD2/LOD3 geometry",
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "STEP file (ISO 10303-21 format)"
                }
            }
        },
        400: {"description": "Invalid file format, missing file/path, or invalid parameters"},
        404: {"description": "Specified gml_path not found on server"},
        413: {"description": "File too large (max 250MB)"},
        500: {"description": "Conversion error (check debug logs for details)"}
    },
)
async def citygml_to_step(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(
        None,
        description="CityGMLファイル（.gml/.xml）をアップロード（file か gml_path のどちらかを指定）",
    ),
    gml_path: Optional[str] = Form(
        None,
        description="サーバーローカルのCityGMLの絶対パス",
        example="/abs/path/to/53394642_bldg_6697_op.gml",
    ),
    limit: Union[int, str, None] = Form(
        None,
        description="処理する建物数の上限（未指定で無制限、正数で制限）",
        example=10,
    ),
    debug: bool = Form(False, description="デバッグログ出力を有効化"),
    method: str = Form(
        "solid",
        description="変換方式：solid（LOD2/3 Solid直接、推奨）, auto（Solid→縫合→押し出しフォールバック）, sew（縫合）, extrude（押し出し）",
    ),
    reproject_to: Optional[str] = Form(
        None,
        description="出力の平面直角/投影座標系（例: EPSG:6676）。未指定で自動選択",
        example="EPSG:6676",
    ),
    source_crs: Optional[str] = Form(
        None,
        description="入力の座標系を明示（例: EPSG:6697）。未指定ならGMLのsrsNameから推定",
        example="EPSG:6697",
    ),
    auto_reproject: bool = Form(
        True,
        description="地理座標系を検出した場合、自動的に適切な投影座標系に変換",
    ),
    precision_mode: str = Form(
        "ultra",
        description="精度モード: standard（標準、0.01%）, high（高精度、0.001%）, maximum（最大精度、0.0001%）, ultra（超高精度、0.00001%、LOD2/LOD3最適化、推奨）, auto（自動）",
        example="ultra",
    ),
    shape_fix_level: str = Form(
        "minimal",
        description="形状修正レベル: minimal（修正最小、ディティール優先、推奨）, standard（標準）, aggressive（修正強化、堅牢性優先）, ultra（最大修正、LOD2/LOD3最適化）",
        example="minimal",
    ),
    building_ids: Optional[str] = Form(
        None,
        description="抽出する建物IDのリスト（カンマ区切り）。未指定で全建物を処理。例: 'bldg_12345,bldg_67890'",
        example="bldg_12345,bldg_67890",
    ),
    filter_attribute: str = Form(
        "gml:id",
        description="building_idsと照合する属性名。'gml:id'（デフォルト）またはgen:genericAttributeのキー名（例: 'buildingID'）",
        example="gml:id",
    ),
):
    """
    CityGML (.gml) を受け取り、高精度な STEP ファイルを生成します。

    Convert CityGML files to STEP format with LOD1/LOD2/LOD3 support.

    **アーキテクチャ / Architecture** (Issue #129):
    - Modular pipeline: 27 components across 7 architectural layers
    - Refactored from monolithic 4,683-line file for maintainability
    - Layers: Core types → Utils → Parsers → Geometry → Transforms → LOD strategies → Pipeline orchestration

    **主要機能 / Key Features**:
    - **LOD Support**: LOD3 → LOD2 → LOD1 hierarchical fallback extraction
    - **BoundedBy Strategy**: 6 surface types (WallSurface, RoofSurface, GroundSurface, etc.)
    - **BuildingPart Merging**: Boolean fusion with automatic hierarchy extraction
    - **XLink Resolution**: Automatic xlink:href reference resolution (Phase 1)
    - **Coordinate Recentering**: CRITICAL - Executed before tolerance calculation to prevent precision loss (Phase 0)
    - **Adaptive Tolerance**: Auto-computed from coordinate range (precision_mode adjustable)
    - **4-Stage Shell Sewing**: Progressive tolerance escalation (10.0→5.0→1.0 multipliers)
    - **4-Level Auto-Repair**: Minimal → Standard → Aggressive → Ultra escalation
    - **CRS Transformation**: Auto-detect and reproject to planar coordinate systems
    - **PLATEAU Optimization**: Japan-specific planar rectangular coordinate system selection

    **入力 / Input**:
    - Upload file OR specify server-side gml_path (one required)
    - Max file size: 250MB (use building_ids filter for larger datasets)

    **変換方式 / Conversion Methods** (method):
    - `solid` (推奨): Direct LOD2/LOD3 Solid extraction - optimized for PLATEAU
    - `auto`: Solid → Sew → Extrude fallback chain
    - `sew`: Surface sewing method (LOD2 boundedBy surfaces)
    - `extrude`: Footprint + height extrusion (LOD0/LOD1 fallback)

    **精度制御 / Precision Control**:
    - `precision_mode`: Tolerance as % of coordinate range
      * `standard`: 0.01% (balanced, recommended)
      * `high`: 0.001% (fine details)
      * `maximum`: 0.0001% (windows, stairs, balconies)
      * `ultra`: 0.00001% (maximum precision, LOD2/LOD3 optimized)
      * `auto`: automatic selection (fallbacks to standard precision)
    - `shape_fix_level`: Geometry repair aggressiveness
      * `minimal`: Minimal fixes, preserve details (recommended)
      * `standard`: Standard repair
      * `aggressive`: Aggressive repair, prioritize robustness
      * `ultra`: Maximum repair with multi-stage escalation

    **建物フィルタリング / Building Filtering**:
    - `building_ids`: Comma-separated building IDs to extract (e.g., "bldg_12345,bldg_67890")
    - `filter_attribute`: Attribute to match against (default: "gml:id", or generic attribute key like "buildingID")
    - Unspecified = process all buildings

    **出力 / Output**:
    - STEP file (ISO 10303-21, AP214CD schema)
    - Units: MM, Precision: 1e-6
    - Custom headers: X-Building-Count, X-Method, X-Precision-Mode, X-Shape-Fix-Level
    """
    tmpdir = None
    out_dir = None
    success = False
    try:
        # Normalize limit parameter (handle empty string from form)
        normalized_limit = normalize_limit_param(limit)

        # Normalize string parameters (handle empty strings)
        normalized_source_crs = source_crs if source_crs and source_crs.strip() else None
        normalized_reproject_to = reproject_to if reproject_to and reproject_to.strip() else None
        normalized_gml_path = gml_path if gml_path and gml_path.strip() else None

        # Normalize precision parameters (handle empty strings, fall back to defaults)
        normalized_precision_mode = precision_mode if precision_mode and precision_mode.strip() else "auto"
        normalized_shape_fix_level = shape_fix_level if shape_fix_level and shape_fix_level.strip() else "standard"

        # Normalize building filtering parameters
        normalized_building_ids = parse_csv_ids(building_ids)

        normalized_filter_attribute = filter_attribute if filter_attribute and filter_attribute.strip() else "gml:id"

        # Validate precision_mode
        valid_precision_modes = ["auto", "standard", "high", "maximum", "ultra"]
        if normalized_precision_mode not in valid_precision_modes:
            raise HTTPException(
                status_code=400,
                detail=f"precision_mode must be one of {valid_precision_modes}, got: {normalized_precision_mode}"
            )

        # Validate shape_fix_level
        valid_shape_fix_levels = ["minimal", "standard", "aggressive", "ultra"]
        if normalized_shape_fix_level not in valid_shape_fix_levels:
            raise HTTPException(
                status_code=400,
                detail=f"shape_fix_level must be one of {valid_shape_fix_levels}, got: {normalized_shape_fix_level}"
            )

        if file is None and not normalized_gml_path:
            raise HTTPException(status_code=400, detail="CityGMLファイルをアップロードするか gml_path を指定してください。")

        # 入力ファイルの用意
        if file is not None:
            if not file.filename.lower().endswith((".gml", ".xml")):
                raise HTTPException(status_code=400, detail="CityGML (.gml/.xml) に対応しています。")

            # ファイルサイズチェック（250MB制限）
            if hasattr(file, 'size') and file.size and file.size > 250 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="ファイルサイズが大きすぎます（最大250MB）。より小さいファイルを使用するか、limitパラメータで処理する建物数を制限してください。"
                )
            tmpdir, in_path, total = await save_upload_to_tmpdir(file, "gml")
            if total == 0:
                raise HTTPException(status_code=400, detail="アップロードされたファイルが空です。")
            print(f"[UPLOAD] /api/citygml/to-step: received {total} bytes -> {in_path}")
        else:
            in_path = normalized_gml_path  # type: ignore
            if not os.path.exists(in_path):
                raise HTTPException(status_code=404, detail=f"指定されたパスが見つかりません: {in_path}")
            print(f"[UPLOAD] /api/citygml/to-step: using local path {in_path}")

        # 出力パス
        out_dir = tempfile.mkdtemp()
        # 入力ファイル名からベース名を取得
        if file is not None:
            base_name = os.path.splitext(os.path.basename(file.filename))[0]
        elif normalized_gml_path:
            base_name = os.path.splitext(os.path.basename(normalized_gml_path))[0]
        else:
            base_name = "citygml"
        output_filename = f"{base_name}.step"
        out_path = os.path.join(out_dir, output_filename)

        ok, msg = export_step_from_citygml(
            in_path,
            out_path,
            limit=normalized_limit,
            debug=debug,
            method=method,
            reproject_to=normalized_reproject_to,
            source_crs=normalized_source_crs,
            auto_reproject=auto_reproject,
            precision_mode=normalized_precision_mode,
            shape_fix_level=normalized_shape_fix_level,
            building_ids=normalized_building_ids,
            filter_attribute=normalized_filter_attribute,
        )
        if not ok:
            raise HTTPException(status_code=400, detail=f"変換に失敗しました: {msg}")

        # ファイルサイズを取得してログ出力
        file_size = os.path.getsize(out_path)
        print(f"[RESPONSE] Generated STEP file: {output_filename} ({file_size:,} bytes)")

        # クリーンアップ関数を定義
        def cleanup_temp_files():
            try:
                if os.path.exists(out_path):
                    os.remove(out_path)
                if os.path.exists(out_dir):
                    os.rmdir(out_dir)
                print(f"[CLEANUP] Removed temporary files: {out_path}")
            except Exception as e:
                print(f"[CLEANUP] Failed to remove temporary files: {e}")

        # レスポンス送信後にクリーンアップをスケジュール
        background_tasks.add_task(cleanup_temp_files)

        # FileResponseを使用して大容量ファイルを効率的にストリーミング
        # Note: CORS headers are automatically handled by CORSMiddleware
        success = True
        return FileResponse(
            path=out_path,
            media_type="application/octet-stream",
            filename=output_filename,
            headers={
                "Cache-Control": "no-cache"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")
    finally:
        # エラー時の一時ディレクトリクリーンアップ
        # 成功時はbackground_tasksが処理するため、エラー時のみクリーンアップ
        if not success:
            cleanup_temp_dir(tmpdir, label="tmpdir")
            cleanup_temp_dir(out_dir, label="out_dir")


# --- CityGML 検証（簡易） ---
@router.post(
    "/api/citygml/validate",
    summary="CityGML Validation",
    tags=["CityGML Processing"],
    responses={
        200: {
            "description": "Validation results with building footprint analysis",
            "content": {
                "application/json": {
                    "example": {
                        "valid": True,
                        "buildings_with_footprints": 42,
                        "sample_building_id": "bldg_001",
                        "notes": "footprint+height extrusion heuristic"
                    }
                }
            }
        },
        400: {"description": "Missing file/path or empty file"},
        404: {"description": "Specified gml_path not found"},
        500: {"description": "Validation error"}
    }
)
async def citygml_validate(
    file: Optional[UploadFile] = File(None, description="CityGML file (.gml/.xml) to validate"),
    gml_path: Optional[str] = Form(None, description="サーバーローカルのCityGMLパス / Server-side CityGML path"),
    limit: Optional[int] = Form(10, description="検証する建物数の上限 / Max buildings to validate"),
):
    """
    CityGML が当モジュールのヒューリスティックに適合するか簡易チェックします。

    Quick validation of CityGML compatibility with this module.

    **検証項目 / Validation Checks**:
    - bldg:Building 要素の存在確認 / Presence of bldg:Building elements
    - フットプリント多角形の取得可否 / Extractable footprint polygons
    - LOD0 FootPrint または RoofEdge の存在 / LOD0 FootPrint or RoofEdge availability

    **用途 / Use Cases**:
    - CityGML → STEP変換の事前チェック
    - 建物数の確認（limitパラメータで制御）
    - サンプル建物IDの取得
    """
    tmpdir = None
    try:
        if file is None and not gml_path:
            raise HTTPException(status_code=400, detail="CityGMLファイルをアップロードするか gml_path を指定してください。")

        if file is not None:
            tmpdir, in_path, total = await save_upload_to_tmpdir(file, "gml")
            if total == 0:
                raise HTTPException(status_code=400, detail="アップロードされたファイルが空です。")
            print(f"[UPLOAD] /api/citygml/validate: received {total} bytes -> {in_path}")
        else:
            in_path = gml_path  # type: ignore
            if not os.path.exists(in_path):
                raise HTTPException(status_code=404, detail=f"指定されたパスが見つかりません: {in_path}")
            print(f"[UPLOAD] /api/citygml/validate: using local path {in_path}")

        fps = parse_citygml_footprints(in_path, limit=limit or None)
        return {
            "valid": len(fps) > 0,
            "buildings_with_footprints": len(fps),
            "sample_building_id": fps[0].building_id if fps else None,
            "notes": "footprint+height extrusion heuristic",
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"検証でエラー: {str(e)}")
    finally:
        cleanup_temp_dir(tmpdir, label="tmpdir")
