import os
import tempfile
import uuid
import zipfile
from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Request, BackgroundTasks
from fastapi.responses import FileResponse, Response, StreamingResponse
from typing import Optional, Union
import io

from config import OCCT_AVAILABLE
from services.step_processor import StepUnfoldGenerator
from models.request_models import BrepPapercraftRequest
from services.citygml_to_step import export_step_from_citygml, parse_citygml_footprints

# APIルーターの作成
router = APIRouter()

# --- STEP専用APIエンドポイント ---
@router.post("/api/step/unfold")
async def unfold_step_to_svg(
    file: UploadFile = File(...),
    return_face_numbers: bool = Form(True),
    output_format: str = Form("svg"),
    layout_mode: str = Form("canvas"),
    page_format: str = Form("A4"),
    page_orientation: str = Form("portrait"),
    scale_factor: float = Form(10.0),
    texture_mappings: Optional[str] = Form(None)
):
    """
    STEPファイル（.step/.stp）を受け取り、展開図（SVG）を生成するAPI。

    Args:
        file: STEPファイル (.step/.stp)
        return_face_numbers: 面番号データを含むかどうか (default: True)
        output_format: 出力形式 - "svg"=SVGファイル、"json"=JSONレスポンス
        layout_mode: レイアウトモード - "canvas"=フリーキャンバス、"paged"=ページ分割 (default: "canvas")
        page_format: ページフォーマット - "A4", "A3", "Letter" (default: "A4")
        page_orientation: ページ方向 - "portrait"=縦、"landscape"=横 (default: "portrait")
        scale_factor: 図の縮尺倍率 (default: 10.0) - 例: 150なら1/150スケール
        texture_mappings: JSON形式のテクスチャマッピング情報 - [{faceNumber, patternId, tileCount}]

    Returns:
        - output_format="svg": 単一SVGファイル（pagedモードでは全ページを縦に並べて表示）
        - output_format="json": JSONレスポンス
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。")
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
            raise HTTPException(status_code=400, detail="STEPファイル（.step/.stp）のみ対応です。")

        # 大容量でも安定するようチャンクで一時保存
        tmpdir = tempfile.mkdtemp()
        file_ext = "step" if file.filename.lower().endswith('.step') else "stp"
        in_path = os.path.join(tmpdir, f"{uuid.uuid4()}.{file_ext}")
        total = 0
        with open(in_path, "wb") as dst:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                total += len(chunk)
                dst.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="アップロードされたファイルが空です。")
        print(f"[UPLOAD] /api/step/unfold: received {total} bytes -> {in_path}")

        # テクスチャマッピングのパース
        parsed_texture_mappings = []
        if texture_mappings:
            try:
                import json
                parsed_texture_mappings = json.loads(texture_mappings)
                print(f"[TEXTURE] Received texture mappings: {parsed_texture_mappings}")
            except json.JSONDecodeError as e:
                print(f"[TEXTURE] Failed to parse texture mappings: {e}")
                # エラーを無視してテクスチャなしで続行

        # StepUnfoldGeneratorインスタンスを作成
        step_unfold_generator = StepUnfoldGenerator()

        # 一時保存したファイルからロード
        if not step_unfold_generator.load_from_file(in_path):
            raise HTTPException(status_code=400, detail="STEPファイルの読み込みに失敗しました。")
        output_path = os.path.join(tempfile.mkdtemp(), f"step_unfold_{uuid.uuid4()}.svg")

        # レイアウトオプションを含むBrepPapercraftRequestを作成
        request = BrepPapercraftRequest(
            layout_mode=layout_mode,
            page_format=page_format,
            page_orientation=page_orientation,
            scale_factor=scale_factor
        )

        # テクスチャマッピングを渡す
        if parsed_texture_mappings:
            step_unfold_generator.set_texture_mappings(parsed_texture_mappings)

        svg_path, stats = step_unfold_generator.generate_brep_papercraft(request, output_path)
        
        # 出力形式に応じてレスポンスを分岐
        if output_format.lower() == "json":
            # JSONレスポンス形式
            with open(svg_path, 'r', encoding='utf-8') as svg_file:
                svg_content = svg_file.read()
            
            response_data = {
                "svg_content": svg_content,
                "stats": stats
            }
            
            try:
                os.unlink(svg_path)
            except:
                pass
            
            # 面番号データを含める場合
            if return_face_numbers:
                face_numbers = step_unfold_generator.get_face_numbers()
                response_data["face_numbers"] = face_numbers
            
            return response_data
        else:
            # SVGファイルレスポンス
            # ページモードでも単一ファイルに全ページが含まれる
            return FileResponse(
                path=svg_path,
                media_type="image/svg+xml",
                filename=f"step_unfold_{layout_mode}_{uuid.uuid4()}.svg",
                headers={
                    "X-Layout-Mode": layout_mode,
                    "X-Page-Format": page_format if layout_mode == "paged" else "N/A",
                    "X-Page-Orientation": page_orientation if layout_mode == "paged" else "N/A",
                    "X-Page-Count": str(stats.get("page_count", 1)) if layout_mode == "paged" else "1"
                }
            )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")

# --- CityGML → STEP 変換エンドポイント ---
@router.post(
    "/api/citygml/to-step",
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
            "description": "STEP file generated successfully"
        }
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
        description="精度モード: auto（標準、0.01%）, high（高精度、0.001%）, maximum（最大精度、0.0001%）, ultra（超高精度、0.00001%、LOD2/LOD3最適化）",
        example="ultra",
    ),
    shape_fix_level: str = Form(
        "ultra",
        description="形状修正レベル: minimal（修正最小、ディティール優先）, standard（標準）, aggressive（修正強化、堅牢性優先）, ultra（最大修正、LOD2/LOD3最適化）",
        example="ultra",
    ),
):
    """
    CityGML (.gml) を受け取り、高精度な STEP ファイルを生成します。

    **主要機能**:
    - gml:Solid ジオメトリ抽出（exterior/interior shells、cavity対応）
    - bldg:BuildingPart 階層構造の自動抽出とマージ
    - XLink参照（xlink:href）の自動解決
    - 適応的tolerance管理（座標範囲の0.01%を自動計算、精度モードで調整可能）
    - 地理座標系を検出した場合、自動的に適切な平面直角座標系に変換
    - 日本のPLATEAUデータの場合、地域に応じた日本平面直角座標系を自動選択
    - STEP出力最適化（AP214CD schema、MM単位、1e-6精度）

    **入力**:
    - アップロードファイルまたはローカルパス (gml_path) のどちらかを指定

    **変換方式** (method):
    - solid（推奨）: LOD2/3 Solid データを直接使用（PLATEAU LOD2/LOD3建物に最適化）
    - auto: LOD2/3 Solid → LOD2表面縫合 → フットプリント押し出し の順で自動フォールバック
    - sew: LOD2の各サーフェスを縫合してソリッド化
    - extrude: フットプリント＋高さ推定から押し出し（LOD0互換用、明示的指定が必要）

    **精度制御** (新機能):
    - precision_mode: 座標範囲に対するtoleranceの割合を制御
      * auto: 0.01% (バランス重視)
      * high: 0.001% (細かいディティール保持)
      * maximum: 0.0001% (最大限の精度、窓枠・階段・バルコニーなどの細部を保持)
      * ultra: 0.00001% (超高精度、LOD2/LOD3最適化、デフォルト)
    - shape_fix_level: 形状修正の強度を制御
      * minimal: 修正を最小限に抑え、細部を優先
      * standard: 標準的な修正
      * aggressive: 修正を強化し、堅牢性を優先
      * ultra: 最大修正、多段階処理、LOD2/LOD3最適化 (デフォルト)
    """
    try:
        # Normalize limit parameter (handle empty string from form)
        normalized_limit: Optional[int] = None
        if limit is not None:
            if isinstance(limit, str):
                if limit.strip() == "" or limit == "0":
                    normalized_limit = None
                else:
                    try:
                        normalized_limit = int(limit)
                    except ValueError:
                        raise HTTPException(status_code=400, detail=f"limit must be a valid integer, got: {limit}")
            elif isinstance(limit, int):
                normalized_limit = limit if limit > 0 else None

        # Normalize string parameters (handle empty strings)
        normalized_source_crs = source_crs if source_crs and source_crs.strip() else None
        normalized_reproject_to = reproject_to if reproject_to and reproject_to.strip() else None
        normalized_gml_path = gml_path if gml_path and gml_path.strip() else None

        # Normalize precision parameters (handle empty strings, fall back to defaults)
        normalized_precision_mode = precision_mode if precision_mode and precision_mode.strip() else "auto"
        normalized_shape_fix_level = shape_fix_level if shape_fix_level and shape_fix_level.strip() else "standard"

        # Validate precision_mode
        valid_precision_modes = ["auto", "high", "maximum", "ultra"]
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
            
            # ファイルサイズチェック（500MB制限）
            if hasattr(file, 'size') and file.size and file.size > 500 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="ファイルサイズが大きすぎます（最大500MB）。より小さいファイルを使用するか、limitパラメータで処理する建物数を制限してください。"
                )
            tmpdir = tempfile.mkdtemp()
            in_path = os.path.join(tmpdir, f"{uuid.uuid4()}.gml")
            total = 0
            with open(in_path, "wb") as f_dst:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    total += len(chunk)
                    f_dst.write(chunk)
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
            base_name = os.path.splitext(file.filename)[0]
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
        return FileResponse(
            path=out_path,
            media_type="application/octet-stream",
            filename=output_filename,
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                "Access-Control-Allow-Credentials": "true",
                "Cache-Control": "no-cache"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")


# --- CityGML 検証（簡易） ---
@router.post("/api/citygml/validate")
async def citygml_validate(
    file: Optional[UploadFile] = File(None),
    gml_path: Optional[str] = Form(None),
    limit: Optional[int] = Form(10),
):
    """
    CityGML が当モジュールのヒューリスティックに適合するか簡易チェックします。
    - bldg:Building が存在し、フットプリント多角形が取得できるかを確認
    """
    try:
        if file is None and not gml_path:
            raise HTTPException(status_code=400, detail="CityGMLファイルをアップロードするか gml_path を指定してください。")

        if file is not None:
            tmpdir = tempfile.mkdtemp()
            in_path = os.path.join(tmpdir, f"{uuid.uuid4()}.gml")
            total = 0
            with open(in_path, "wb") as f_dst:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    total += len(chunk)
                    f_dst.write(chunk)
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

# --- ヘルスチェック ---
@router.get("/api/health", status_code=200)
async def api_health_check():
    return {
        "status": "healthy" if OCCT_AVAILABLE else "degraded",
        "version": "1.0.0",
        "opencascade_available": OCCT_AVAILABLE,
        "supported_formats": ["step", "stp", "brep"] if OCCT_AVAILABLE else [],
        "features": {
            "step_to_svg_unfold": OCCT_AVAILABLE,
            "face_numbering": True,
            "multi_page_layout": True,
            "canvas_layout": True,
            "paged_layout": True
        }
    }
