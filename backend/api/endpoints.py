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
from models.request_models import (
    BrepPapercraftRequest,
    PlateauSearchRequest,
    PlateauFetchAndConvertRequest,
    PlateauSearchResponse,
    BuildingInfoResponse,
    GeocodingResultResponse,
    PlateauBuildingIdRequest,
    PlateauBuildingIdSearchResponse,
    PlateauBuildingIdWithMeshRequest
)
from services.citygml_to_step import export_step_from_citygml, parse_citygml_footprints
from services.plateau_fetcher import search_buildings_by_address, search_building_by_id, search_building_by_id_and_mesh

# APIルーターの作成
router = APIRouter()

# --- STEP専用APIエンドポイント ---
@router.post("/api/step/unfold")
async def unfold_step_to_svg(
    file: UploadFile = File(...),
    return_face_numbers: bool = Form(True),
    output_format: str = Form("svg"),
    layout_mode: str = Form("paged"),
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

            # 警告情報を含める
            if "warnings" in stats and stats["warnings"]:
                response_data["warnings"] = stats["warnings"]

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

# --- STEP → PDF 展開図エンドポイント ---
@router.post("/api/step/unfold-pdf")
async def unfold_step_to_pdf(
    file: UploadFile = File(...),
    layout_mode: str = Form("paged"),
    page_format: str = Form("A4"),
    page_orientation: str = Form("portrait"),
    scale_factor: float = Form(150.0),
    texture_mappings: Optional[str] = Form(None)
):
    """
    STEPファイル（.step/.stp）を受け取り、展開図をPDF形式で生成するAPI。

    Args:
        file: STEPファイル (.step/.stp)
        layout_mode: レイアウトモード - "canvas"=フリーキャンバス、"paged"=ページ分割 (default: "paged")
        page_format: ページフォーマット - "A4", "A3", "Letter" (default: "A4")
        page_orientation: ページ方向 - "portrait"=縦、"landscape"=横 (default: "portrait")
        scale_factor: 図の縮尺倍率 (default: 150.0) - 例: 150なら1/150スケール
        texture_mappings: JSON形式のテクスチャマッピング情報 - [{faceNumber, patternId, tileCount}]

    Returns:
        PDFファイル（application/pdf）
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。")

    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
            raise HTTPException(status_code=400, detail="STEPファイル（.step/.stp）のみ対応です。")

        # 一時ディレクトリ作成
        tmpdir = tempfile.mkdtemp()
        file_ext = "step" if file.filename.lower().endswith('.step') else "stp"
        in_path = os.path.join(tmpdir, f"{uuid.uuid4()}.{file_ext}")

        # ファイル保存
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

        print(f"[UPLOAD] /api/step/unfold-pdf: received {total} bytes -> {in_path}")

        # テクスチャマッピングのパース
        parsed_texture_mappings = []
        if texture_mappings:
            try:
                import json
                parsed_texture_mappings = json.loads(texture_mappings)
                print(f"[TEXTURE] Parsed {len(parsed_texture_mappings)} texture mappings")
            except json.JSONDecodeError as e:
                print(f"[TEXTURE] Warning: Failed to parse texture_mappings: {e}")

        # PDF生成 - SVGエンドポイントと同じロジックを使用
        generator = StepUnfoldGenerator()
        if not generator.load_from_file(in_path):
            raise HTTPException(status_code=400, detail="STEPファイルの読み込みに失敗しました。")

        # BrepPapercraftRequestを作成（SVGエンドポイントと同じパラメータを使用）
        # これによりmax_faces=20（デフォルト値）が使用され、SVGと同じレイアウトになる
        request = BrepPapercraftRequest(
            layout_mode=layout_mode,
            page_format=page_format,
            page_orientation=page_orientation,
            scale_factor=scale_factor
        )

        # テクスチャマッピングを設定
        if parsed_texture_mappings:
            generator.set_texture_mappings(parsed_texture_mappings)

        # SVGエンドポイントと同じパイプラインを実行（max_faces=20を使用）
        # 1. BREPトポロジ解析
        generator.analyze_brep_topology()

        # 2. パラメータ設定
        generator.scale_factor = request.scale_factor
        generator.layout_mode = request.layout_mode
        generator.page_format = request.page_format
        generator.page_orientation = request.page_orientation

        # SVGエクスポーターとレイアウトマネージャーにも設定を反映（重要！）
        generator.svg_exporter.scale_factor = request.scale_factor
        generator.svg_exporter.layout_mode = request.layout_mode
        generator.svg_exporter.page_format = request.page_format
        generator.svg_exporter.page_orientation = request.page_orientation
        generator.layout_manager.scale_factor = request.scale_factor

        # 3. 展開可能面のグルーピング（SVGと同じmax_facesを使用）
        generator.group_faces_for_unfolding(request.max_faces)

        # 4. 各グループの2D展開
        unfolded_groups = generator.unfold_face_groups()

        # レイアウト処理
        if layout_mode == "paged":
            # 5. ページモード: ページ単位でレイアウト
            generator.layout_manager.update_page_settings(
                page_format=request.page_format,
                page_orientation=request.page_orientation
            )
            paged_groups, warnings = generator.layout_manager.layout_for_pages(unfolded_groups)

            # PDFファイルパス
            pdf_path = os.path.join(tmpdir, f"unfold_{uuid.uuid4()}.pdf")

            # 6. PDFエクスポート
            result_path = generator.export_to_pdf_paged(paged_groups, pdf_path)

            print(f"[PDF] Generated PDF with {len(paged_groups)} pages: {result_path}")

            # PDFファイルを返す
            return FileResponse(
                path=result_path,
                media_type="application/pdf",
                filename=f"step_unfold_{page_format}_{page_orientation}_{uuid.uuid4()}.pdf",
                headers={
                    "X-Layout-Mode": layout_mode,
                    "X-Page-Format": page_format,
                    "X-Page-Orientation": page_orientation,
                    "X-Page-Count": str(len(paged_groups)),
                    "X-Scale-Factor": str(scale_factor)
                }
            )
        else:
            # canvasモードは現時点ではサポートしない（単一ページSVG→PDFは将来実装可能）
            raise HTTPException(
                status_code=400,
                detail="PDF出力は現在 layout_mode='paged' のみサポートしています。"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDFエクスポートエラー: {str(e)}")

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
        description="精度モード: standard（標準、0.01%）, high（高精度、0.001%）, maximum（最大精度、0.0001%）, ultra（超高精度、0.00001%、LOD2/LOD3最適化、推奨）",
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
      * standard: 0.01% (バランス重視、推奨・デフォルト)
      * high: 0.001% (細かいディティール保持)
      * maximum: 0.0001% (最大限の精度、窓枠・階段・バルコニーなどの細部を保持)
      * ultra: 0.00001% (超高精度、LOD2/LOD3最適化、完璧なデータ用)
    - shape_fix_level: 形状修正の強度を制御
      * minimal: 修正を最小限に抑え、細部を優先 (推奨・デフォルト)
      * standard: 標準的な修正
      * aggressive: 修正を強化し、堅牢性を優先
      * ultra: 最大修正、多段階処理、LOD2/LOD3最適化 (完璧なデータ用)

    **建物フィルタリング** (新機能):
    - building_ids: 処理する建物IDのリスト（カンマ区切り）
      * 未指定の場合、全建物を処理
      * 例: "bldg_12345,bldg_67890"
    - filter_attribute: building_idsと照合する属性
      * gml:id (デフォルト): 標準のGML識別子で照合
      * 汎用属性名: gen:genericAttributeの値で照合（例: "buildingID"）
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

        # Normalize building filtering parameters
        normalized_building_ids: Optional[list[str]] = None
        if building_ids and building_ids.strip():
            # Split by comma and strip whitespace from each ID
            normalized_building_ids = [bid.strip() for bid in building_ids.split(",") if bid.strip()]
            if not normalized_building_ids:
                normalized_building_ids = None

        normalized_filter_attribute = filter_attribute if filter_attribute and filter_attribute.strip() else "gml:id"

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


# --- PLATEAU Address Search ---
@router.post("/api/plateau/search-by-address", response_model=PlateauSearchResponse)
async def plateau_search_by_address(
    request: PlateauSearchRequest
):
    """
    住所または施設名からPLATEAU建物を検索します。

    Search for PLATEAU buildings by address or facility name.

    **処理フロー / Process Flow:**
    1. OpenStreetMap Nominatim APIで住所→座標変換
    2. PLATEAU Data Catalog APIから周辺のCityGMLデータを取得
    3. 建物情報を抽出・パース
    4. 距離順にソート

    **入力例 / Example Inputs:**
    - 施設名: "東京駅", "渋谷スクランブルスクエア"
    - 完全住所: "東京都千代田区丸の内1-9-1"
    - 部分住所: "千代田区丸の内"
    - 郵便番号: "100-0005"

    **レート制限 / Rate Limits:**
    - Nominatim: 1リクエスト/秒（自動的に適用）

    Args:
        request: PlateauSearchRequest containing query, radius, limit, etc.

    Returns:
        PlateauSearchResponse with geocoding info and list of buildings

    Example:
        ```json
        {
            "query": "東京駅",
            "radius": 0.001,
            "limit": 10
        }
        ```
    """
    try:
        print(f"\n{'='*60}")
        print(f"[API] /api/plateau/search-by-address")
        print(f"[API] Query: {request.query}")
        print(f"[API] Radius: {request.radius} degrees")
        print(f"[API] Limit: {request.limit}")
        print(f"{'='*60}\n")

        # Call the search function with name_filter and search_mode
        result = search_buildings_by_address(
            query=request.query,
            radius=request.radius,
            limit=request.limit,
            name_filter=request.name_filter,
            search_mode=request.search_mode or "hybrid"
        )

        if not result["success"]:
            # Return error response
            return PlateauSearchResponse(
                success=False,
                geocoding=None,
                buildings=[],
                found_count=0,
                search_mode=result.get("search_mode", "hybrid"),
                error=result.get("error", "Unknown error")
            )

        # Convert to response models
        geocoding_data = result["geocoding"]
        geocoding_response = GeocodingResultResponse(
            query=geocoding_data.query,
            latitude=geocoding_data.latitude,
            longitude=geocoding_data.longitude,
            display_name=geocoding_data.display_name,
            osm_type=geocoding_data.osm_type,
            osm_id=geocoding_data.osm_id
        ) if geocoding_data else None

        buildings_response = [
            BuildingInfoResponse(
                building_id=b.building_id,
                gml_id=b.gml_id,
                latitude=b.latitude,
                longitude=b.longitude,
                distance_meters=b.distance_meters,
                height=b.height,
                usage=b.usage,
                measured_height=b.measured_height,
                name=b.name,
                relevance_score=b.relevance_score,
                name_similarity=b.name_similarity,
                match_reason=b.match_reason,
                has_lod2=b.has_lod2,
                has_lod3=b.has_lod3
            )
            for b in result["buildings"]
        ]

        return PlateauSearchResponse(
            success=True,
            geocoding=geocoding_response,
            buildings=buildings_response,
            found_count=len(buildings_response),
            search_mode=result.get("search_mode", "hybrid"),
            error=None
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"検索エラー: {str(e)}")


@router.post("/api/plateau/fetch-and-convert")
async def plateau_fetch_and_convert(
    background_tasks: BackgroundTasks,
    query: str = Form(..., description="住所または施設名"),
    radius: float = Form(0.001, description="検索半径（度）"),
    auto_select_nearest: bool = Form(True, description="最近傍建物を自動選択"),
    building_limit: Union[int, str, None] = Form(None, description="変換する建物数（未指定で無制限）"),
    building_ids: Optional[str] = Form(None, description="ユーザーが選択した建物IDのリスト（カンマ区切り）"),
    debug: bool = Form(False, description="デバッグモード"),
    method: str = Form("solid", description="変換方式"),
    auto_reproject: bool = Form(True, description="自動再投影"),
    precision_mode: str = Form("ultra", description="精度モード（推奨: ultra）"),
    shape_fix_level: str = Form("minimal", description="形状修正レベル（推奨: minimal）"),
    merge_building_parts: bool = Form(False, description="BuildingPartを単一ソリッドに結合（詳細保持優先: False推奨）"),
):
    """
    住所・施設名から自動的にPLATEAU建物を取得してSTEPファイルに変換します。

    Automatically fetch PLATEAU buildings by address/facility name and convert to STEP.

    **ワンステップ処理 / One-Step Process:**
    1. 住所検索（Nominatim）
    2. CityGML取得（PLATEAU API） ← 1回のみ
    3. 最近傍建物特定
    4. STEP変換（取得済みCityGMLを再利用）
    5. ファイル返却

    **入力例 / Example:**
    - query: "東京駅"
    - radius: 0.001 (約100m)
    - building_limit: 1 (最近傍の1棟のみ)

    **利点 / Benefits:**
    - ✅ CityGMLファイルの手動ダウンロード不要
    - ✅ 必要な建物のみを取得（軽量）
    - ✅ 常に最新のPLATEAUデータを使用

    Returns:
        STEPファイル（application/octet-stream）
    """
    try:
        # Normalize building_limit parameter (handle empty string, "0", or None)
        normalized_building_limit: Optional[int] = None
        if building_limit is not None:
            if isinstance(building_limit, str):
                if building_limit.strip() == "" or building_limit == "0":
                    normalized_building_limit = None
                else:
                    try:
                        normalized_building_limit = int(building_limit)
                        if normalized_building_limit <= 0:
                            normalized_building_limit = None
                    except ValueError:
                        raise HTTPException(
                            status_code=400,
                            detail=f"building_limit must be a valid positive integer, got: {building_limit}"
                        )
            elif isinstance(building_limit, int):
                normalized_building_limit = building_limit if building_limit > 0 else None

        # Normalize building_ids parameter (comma-separated string to list)
        normalized_building_ids: Optional[list[str]] = None
        if building_ids and building_ids.strip():
            normalized_building_ids = [bid.strip() for bid in building_ids.split(",") if bid.strip()]
            if not normalized_building_ids:
                normalized_building_ids = None

        print(f"\n{'='*60}")
        print(f"[API] /api/plateau/fetch-and-convert")
        print(f"[API] Query: {query}")
        print(f"[API] Radius: {radius} degrees")
        print(f"[API] Building limit: {normalized_building_limit if normalized_building_limit else 'unlimited'}")
        print(f"[API] User-selected building IDs: {normalized_building_ids if normalized_building_ids else 'None (auto-select)'}")
        print(f"{'='*60}\n")

        # Step 1: Search for buildings
        search_result = search_buildings_by_address(
            query=query,
            radius=radius,
            limit=normalized_building_limit if auto_select_nearest else None
        )

        if not search_result["success"]:
            raise HTTPException(
                status_code=404,
                detail=search_result.get("error", "建物が見つかりませんでした")
            )

        buildings = search_result["buildings"]
        if not buildings:
            raise HTTPException(
                status_code=404,
                detail=f"指定された場所に建物が見つかりませんでした: {query}"
            )

        # Step 2: Extract gml:id list from user selection OR smart-selected buildings
        if normalized_building_ids:
            # User explicitly selected specific buildings - use those IDs directly
            final_building_ids = normalized_building_ids
            print(f"[API] Using {len(final_building_ids)} user-selected building(s):")

            # Find LOD information for selected buildings
            for i, bid in enumerate(final_building_ids, 1):
                # Find matching building in search results to get LOD info
                matching_building = next((b for b in buildings if b.gml_id == bid), None)
                if matching_building:
                    lod_str = []
                    if matching_building.has_lod3:
                        lod_str.append("LOD3")
                    if matching_building.has_lod2:
                        lod_str.append("LOD2")
                    if not lod_str:
                        lod_str.append("LOD1 or lower")

                    height = matching_building.measured_height or matching_building.height or 0
                    name_str = f'"{matching_building.name}"' if matching_building.name else "unnamed"
                    print(f"[API LOD INFO]   {i}. {name_str} ({', '.join(lod_str)})")
                    print(f"[API LOD INFO]      ID: {bid[:50]}...")
                    print(f"[API LOD INFO]      Height: {height:.1f}m, Distance: {matching_building.distance_meters:.1f}m")
                else:
                    print(f"[API]   {i}. {bid[:50]}... (LOD info unavailable)")
        else:
            # No user selection - fall back to auto-selection from search results
            selected_buildings = buildings[:normalized_building_limit] if normalized_building_limit else buildings
            final_building_ids = [b.gml_id for b in selected_buildings]  # Always use gml:id

            print(f"[API] Auto-selected {len(final_building_ids)} building(s) by smart scoring:")
            for i, (bid, b) in enumerate(zip(final_building_ids, selected_buildings), 1):
                lod_str = []
                if b.has_lod3:
                    lod_str.append("LOD3")
                if b.has_lod2:
                    lod_str.append("LOD2")
                if not lod_str:
                    lod_str.append("LOD1 or lower")

                height = b.measured_height or b.height or 0
                name_str = f'"{b.name}"' if b.name else "unnamed"
                print(f"[API LOD INFO]   {i}. {name_str} ({', '.join(lod_str)}) - {height:.1f}m, {b.distance_meters:.1f}m away")
                print(f"[API LOD INFO]      ID: {bid[:30]}...")

        # Step 3: Reuse CityGML XML from search results (no re-fetch needed!)
        xml_content = search_result.get("citygml_xml")

        if not xml_content:
            raise HTTPException(
                status_code=500,
                detail="CityGMLデータの取得に失敗しました"
            )

        print(f"[API] Reusing CityGML from search results ({len(xml_content):,} bytes)")

        # Step 4: Save CityGML to temp file
        tmpdir = tempfile.mkdtemp()
        gml_path = os.path.join(tmpdir, f"{uuid.uuid4()}.gml")
        with open(gml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        # Step 5: Convert to STEP with gml:id filtering
        out_dir = tempfile.mkdtemp()
        # Use ASCII-safe filename (HTTP headers don't support non-ASCII characters)
        output_filename = "plateau_building.step"
        out_path = os.path.join(out_dir, output_filename)

        ok, msg = export_step_from_citygml(
            gml_path,
            out_path,
            limit=None,  # Don't use limit - we filter by building_ids instead
            debug=debug,
            method=method,
            auto_reproject=auto_reproject,
            precision_mode=precision_mode,
            shape_fix_level=shape_fix_level,
            merge_building_parts=merge_building_parts,
            # Use gml:id filtering (consistent, no mixed ID types)
            building_ids=final_building_ids,
            filter_attribute="gml:id",
        )

        if not ok:
            raise HTTPException(
                status_code=500,
                detail=f"STEP変換に失敗しました: {msg}"
            )

        # Step 6: Return STEP file
        file_size = os.path.getsize(out_path)
        print(f"[API] Success: Generated {output_filename} ({file_size:,} bytes)")

        # Cleanup function
        def cleanup_temp_files():
            try:
                if os.path.exists(gml_path):
                    os.remove(gml_path)
                if os.path.exists(tmpdir):
                    os.rmdir(tmpdir)
                if os.path.exists(out_path):
                    os.remove(out_path)
                if os.path.exists(out_dir):
                    os.rmdir(out_dir)
                print(f"[CLEANUP] Removed temporary files")
            except Exception as e:
                print(f"[CLEANUP] Failed: {e}")

        background_tasks.add_task(cleanup_temp_files)

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


# --- PLATEAU: Building ID Search ---
@router.post("/api/plateau/search-by-id", response_model=PlateauBuildingIdSearchResponse)
async def plateau_search_by_building_id(request: PlateauBuildingIdRequest):
    """
    Search for a specific PLATEAU building by its building ID.

    Args:
        request: PlateauBuildingIdRequest with building_id

    Returns:
        PlateauBuildingIdSearchResponse with building information or error details

    Example:
        POST /api/plateau/search-by-id
        {
            "building_id": "13101-bldg-2287"
        }
    """
    try:
        print(f"\n{'='*60}")
        print(f"[API] /api/plateau/search-by-id")
        print(f"[API] Building ID: {request.building_id}")
        print(f"{'='*60}\n")

        # Search for building by ID
        result = search_building_by_id(request.building_id, debug=request.debug)

        if not result["success"]:
            return PlateauBuildingIdSearchResponse(
                success=False,
                building=None,
                municipality_code=result.get("municipality_code"),
                municipality_name=result.get("municipality_name"),
                citygml_file=result.get("citygml_file"),
                total_buildings_in_file=result.get("total_buildings_in_file"),
                error=result.get("error"),
                error_details=result.get("error_details")
            )

        # Success: Return building information
        return PlateauBuildingIdSearchResponse(
            success=True,
            building=result["building"],
            municipality_code=result["municipality_code"],
            municipality_name=result["municipality_name"],
            citygml_file=result.get("citygml_file"),
            total_buildings_in_file=result["total_buildings_in_file"],
            error=None,
            error_details=None
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return PlateauBuildingIdSearchResponse(
            success=False,
            building=None,
            error="Internal server error",
            error_details=f"予期しないエラー: {str(e)}"
        )


@router.post("/api/plateau/fetch-by-id")
async def plateau_fetch_by_building_id(request: PlateauBuildingIdRequest):
    """
    Fetch PLATEAU building by ID and convert to STEP format.

    This endpoint combines search and conversion in one step:
    1. Searches for building by ID
    2. Converts the building to STEP format
    3. Returns STEP file

    Args:
        request: PlateauBuildingIdRequest with building_id and conversion options

    Returns:
        STEP file as application/octet-stream

    Example:
        POST /api/plateau/fetch-by-id
        {
            "building_id": "13101-bldg-2287",
            "precision_mode": "ultra",
            "shape_fix_level": "minimal"
        }
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OpenCASCADE が利用できません。STEPファイルの変換には OpenCASCADE が必要です。"
        )

    try:
        print(f"\n{'='*60}")
        print(f"[API] /api/plateau/fetch-by-id")
        print(f"[API] Building ID: {request.building_id}")
        print(f"[API] Precision Mode: {request.precision_mode}")
        print(f"[API] Shape Fix Level: {request.shape_fix_level}")
        print(f"{'='*60}\n")

        # Step 1: Search for building by ID
        search_result = search_building_by_id(request.building_id, debug=request.debug)

        if not search_result["success"]:
            error_msg = search_result.get("error", "Building not found")
            error_details = search_result.get("error_details", "")
            raise HTTPException(
                status_code=404,
                detail=f"{error_msg}. {error_details}"
            )

        # Step 2: Convert to STEP
        citygml_xml = search_result.get("citygml_xml")
        if not citygml_xml:
            raise HTTPException(
                status_code=500,
                detail="CityGML data is missing from search result"
            )

        # Save CityGML to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gml', delete=False, encoding='utf-8') as tmp_gml:
            tmp_gml.write(citygml_xml)
            tmp_gml_path = tmp_gml.name

        # Create temporary STEP output file
        step_file_name = f"{request.building_id.replace('-', '_')}.step"
        tmp_step_path = os.path.join(tempfile.gettempdir(), step_file_name)

        try:
            # Export to STEP with specified building ID filter
            success, message = export_step_from_citygml(
                tmp_gml_path,
                tmp_step_path,
                building_ids=[request.building_id],
                filter_attribute="gml:id",
                method=request.method,
                auto_reproject=request.auto_reproject,
                precision_mode=request.precision_mode,
                shape_fix_level=request.shape_fix_level,
                merge_building_parts=request.merge_building_parts,
                debug=request.debug
            )

            if not success:
                raise HTTPException(status_code=500, detail=f"CityGML to STEP conversion failed: {message}")

            # Verify STEP file exists
            if not os.path.exists(tmp_step_path):
                raise HTTPException(status_code=500, detail="STEP file was not created")

            # Return STEP file
            print(f"[API] Success: Returning STEP file for building {request.building_id}")
            return FileResponse(
                path=tmp_step_path,
                media_type="application/octet-stream",
                filename=step_file_name,
                background=BackgroundTasks()
            )

        finally:
            # Clean up temporary CityGML file
            if os.path.exists(tmp_gml_path):
                os.remove(tmp_gml_path)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")


# --- PLATEAU: Building ID + Mesh Code Search (Optimized) ---
@router.post("/api/plateau/search-by-id-and-mesh", response_model=PlateauBuildingIdSearchResponse)
async def plateau_search_by_id_and_mesh(request: PlateauBuildingIdWithMeshRequest):
    """
    Search for a specific PLATEAU building by building ID + mesh code (optimized).

    This endpoint is much faster than /api/plateau/search-by-id because it only
    downloads 1km² area instead of the entire municipality.

    Args:
        request: PlateauBuildingIdWithMeshRequest with building_id and mesh_code

    Returns:
        PlateauBuildingIdSearchResponse with building information or error details

    Example:
        POST /api/plateau/search-by-id-and-mesh
        {
            "building_id": "13101-bldg-2287",
            "mesh_code": "53394511"
        }
    """
    try:
        print(f"\n{'='*60}")
        print(f"[API] /api/plateau/search-by-id-and-mesh")
        print(f"[API] Building ID: {request.building_id}")
        print(f"[API] Mesh Code: {request.mesh_code}")
        print(f"{'='*60}\n")

        # Search for building by ID + mesh code
        result = search_building_by_id_and_mesh(
            request.building_id,
            request.mesh_code,
            debug=request.debug
        )

        if not result["success"]:
            return PlateauBuildingIdSearchResponse(
                success=False,
                building=None,
                municipality_code=None,  # Not used in mesh-based search
                municipality_name=None,
                citygml_file=None,
                total_buildings_in_file=result.get("total_buildings_in_mesh"),
                error=result.get("error"),
                error_details=result.get("error_details")
            )

        # Success: Return building information
        return PlateauBuildingIdSearchResponse(
            success=True,
            building=result["building"],
            municipality_code=None,  # Not extracted in mesh-based search
            municipality_name=None,
            citygml_file=None,
            total_buildings_in_file=result["total_buildings_in_mesh"],
            error=None,
            error_details=None
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return PlateauBuildingIdSearchResponse(
            success=False,
            building=None,
            error="Internal server error",
            error_details=f"予期しないエラー: {str(e)}"
        )


@router.post("/api/plateau/fetch-by-id-and-mesh")
async def plateau_fetch_by_id_and_mesh(request: PlateauBuildingIdWithMeshRequest):
    """
    Fetch PLATEAU building by ID + mesh code and convert to STEP format (optimized).

    This endpoint is much faster than /api/plateau/fetch-by-id because it only
    downloads 1km² area instead of the entire municipality.

    Args:
        request: PlateauBuildingIdWithMeshRequest with building_id, mesh_code, and conversion options

    Returns:
        STEP file as application/octet-stream

    Example:
        POST /api/plateau/fetch-by-id-and-mesh
        {
            "building_id": "13101-bldg-2287",
            "mesh_code": "53394511",
            "precision_mode": "ultra",
            "shape_fix_level": "minimal"
        }
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OpenCASCADE が利用できません。STEPファイルの変換には OpenCASCADE が必要です。"
        )

    try:
        print(f"\n{'='*60}")
        print(f"[API] /api/plateau/fetch-by-id-and-mesh")
        print(f"[API] Building ID: {request.building_id}")
        print(f"[API] Mesh Code: {request.mesh_code}")
        print(f"[API] Precision Mode: {request.precision_mode}")
        print(f"[API] Shape Fix Level: {request.shape_fix_level}")
        print(f"{'='*60}\n")

        # Step 1: Search for building by ID + mesh code
        search_result = search_building_by_id_and_mesh(
            request.building_id,
            request.mesh_code,
            debug=request.debug
        )

        if not search_result["success"]:
            error_msg = search_result.get("error", "Building not found")
            error_details = search_result.get("error_details", "")
            raise HTTPException(
                status_code=404,
                detail=f"{error_msg}. {error_details}"
            )

        # Step 2: Convert to STEP
        citygml_xml = search_result.get("citygml_xml")
        if not citygml_xml:
            raise HTTPException(
                status_code=500,
                detail="CityGML data is missing from search result"
            )

        # Save CityGML to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gml', delete=False, encoding='utf-8') as tmp_gml:
            tmp_gml.write(citygml_xml)
            tmp_gml_path = tmp_gml.name

        # Create temporary STEP output file
        step_file_name = f"{request.building_id.replace('-', '_')}.step"
        tmp_step_path = os.path.join(tempfile.gettempdir(), step_file_name)

        try:
            # Export to STEP with specified building ID filter
            success, message = export_step_from_citygml(
                tmp_gml_path,
                tmp_step_path,
                building_ids=[request.building_id],
                filter_attribute="gml:id",
                method=request.method,
                auto_reproject=request.auto_reproject,
                precision_mode=request.precision_mode,
                shape_fix_level=request.shape_fix_level,
                merge_building_parts=request.merge_building_parts,
                debug=request.debug
            )

            if not success:
                raise HTTPException(status_code=500, detail=f"CityGML to STEP conversion failed: {message}")

            # Verify STEP file exists
            if not os.path.exists(tmp_step_path):
                raise HTTPException(status_code=500, detail="STEP file was not created")

            # Return STEP file
            print(f"[API] Success: Returning STEP file for building {request.building_id}")
            return FileResponse(
                path=tmp_step_path,
                media_type="application/octet-stream",
                filename=step_file_name,
                background=BackgroundTasks()
            )

        finally:
            # Clean up temporary CityGML file
            if os.path.exists(tmp_gml_path):
                os.remove(tmp_gml_path)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")


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

# --- デバッグ: CORS設定確認 ---
@router.get("/api/debug/cors-config")
async def debug_cors_config():
    """
    CORS設定の診断情報を返す（デバッグ用）

    **警告**: 本番環境では検証後にこのエンドポイントを削除することを推奨

    Returns:
        dict: 現在のCORS設定とレスポンスヘッダーのプレビュー
    """
    import os
    from config import FRONTEND_URL, CORS_ALLOW_ALL

    # 環境変数の生の値を取得
    raw_frontend_url = os.getenv("FRONTEND_URL")
    raw_cors_allow_all = os.getenv("CORS_ALLOW_ALL")

    # 設定の解釈結果
    is_dev_mode = CORS_ALLOW_ALL or FRONTEND_URL == "*"
    cors_mode = "development (localhost only)" if is_dev_mode else "production (restricted origins)"

    # 許可されるオリジンを構築（config.pyと同じロジック）
    if is_dev_mode:
        allowed_origins = [
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
        ]
    else:
        allowed_origins = [
            "https://paper-cad.soynyuu.com",
            "https://app-paper-cad.soynyuu.com",
        ]
        if FRONTEND_URL and FRONTEND_URL != "*":
            if FRONTEND_URL not in allowed_origins:
                allowed_origins.insert(0, FRONTEND_URL)

    return {
        "cors_configuration": {
            "mode": cors_mode,
            "frontend_url": FRONTEND_URL,
            "cors_allow_all": CORS_ALLOW_ALL,
            "is_production_safe": not is_dev_mode,
            "allowed_origins": allowed_origins,
            "allows_credentials": True
        },
        "environment_variables": {
            "FRONTEND_URL": raw_frontend_url,
            "CORS_ALLOW_ALL": raw_cors_allow_all
        },
        "expected_response_headers": {
            "access-control-allow-origin": f"{allowed_origins[0]} (or matching request origin)",
            "access-control-allow-credentials": "true",
            "access-control-allow-methods": "*",
            "access-control-allow-headers": "*"
        },
        "security_notes": {
            "wildcard_not_used": "Wildcard origin (*) is never used with credentials for security compliance",
            "rfc_6454_compliance": "Complies with CORS spec (RFC 6454) - no wildcard + credentials combination"
        },
        "warning": "This endpoint should be removed in production after verification"
    }
