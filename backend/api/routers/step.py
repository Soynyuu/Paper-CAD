import os
import tempfile
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.helpers import cleanup_temp_dir, save_upload_to_tmpdir
from config import OCCT_AVAILABLE
from models.request_models import BrepPapercraftRequest
from services.step_processor import StepUnfoldGenerator

router = APIRouter()


# --- STEP専用APIエンドポイント ---
@router.post(
    "/api/step/unfold",
    summary="STEP → SVG Unfold",
    tags=["STEP Processing"],
    responses={
        200: {
            "description": "SVG file or JSON response with unfold data",
            "content": {
                "image/svg+xml": {
                    "example": "SVG file content with unfold layout"
                },
                "application/json": {
                    "example": {
                        "svg_content": "<svg>...</svg>",
                        "stats": {"page_count": 3, "total_faces": 42},
                        "face_numbers": [1, 2, 3]
                    }
                }
            }
        },
        400: {"description": "Invalid file format or parameters"},
        503: {"description": "OpenCASCADE not available"}
    }
)
async def unfold_step_to_svg(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="STEP file (.step/.stp)"),
    return_face_numbers: bool = Form(True, description="面番号データを含む / Include face numbers"),
    output_format: str = Form("svg", description="出力形式 / Output format (svg/json)"),
    layout_mode: str = Form("paged", description="レイアウトモード / Layout mode (canvas/paged)"),
    page_format: str = Form("A4", description="ページフォーマット / Page format (A4/A3/Letter)"),
    page_orientation: str = Form("portrait", description="ページ向き / Orientation (portrait/landscape)"),
    scale_factor: float = Form(10.0, description="縮尺倍率 / Scale factor (例: 150=1/150)"),
    texture_mappings: Optional[str] = Form(None, description="テクスチャマッピング情報（JSON） / Texture mappings (JSON)")
):
    """
    STEPファイル（.step/.stp）を受け取り、展開図（SVG）を生成するAPI。

    Unfold 3D STEP file to 2D SVG papercraft template.

    **レイアウトモード / Layout Modes**:
    - `canvas`: フリーキャンバス（全面を1枚に配置） / Free canvas (all faces on one page)
    - `paged`: ページ分割（A4/A3/Letterサイズに自動配置） / Paginated layout

    **出力形式 / Output Format**:
    - `svg`: SVGファイル（pagedモードでは全ページを縦に並べて表示） / SVG file (all pages stacked vertically in paged mode)
    - `json`: JSONレスポンス（SVGコンテンツと統計情報） / JSON response with SVG content and stats

    Args:
        file: STEPファイル / STEP file (.step/.stp)
        return_face_numbers: 面番号データを含む / Include face numbers (default: True)
        output_format: 出力形式 / Output format (svg/json, default: "svg")
        layout_mode: レイアウトモード / Layout mode (canvas/paged, default: "paged")
        page_format: ページフォーマット / Page format (A4/A3/Letter, default: "A4")
        page_orientation: ページ向き / Orientation (portrait/landscape, default: "portrait")
        scale_factor: 縮尺倍率 / Scale factor (例: 150 = 1/150 scale, default: 10.0)
        texture_mappings: テクスチャマッピング情報（JSON） / Texture mappings (JSON array)

    Returns:
        - output_format="svg": SVGファイル / SVG file
        - output_format="json": JSONレスポンス / JSON response with SVG content and statistics
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。")

    tmpdir = None
    output_tmpdir = None
    success = False
    cleanup_in_background = False
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
            raise HTTPException(status_code=400, detail="STEPファイル（.step/.stp）のみ対応です。")

        # 大容量でも安定するようチャンクで一時保存
        file_ext = "step" if file.filename.lower().endswith('.step') else "stp"
        tmpdir, in_path, total = await save_upload_to_tmpdir(file, file_ext)
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
        output_tmpdir = tempfile.mkdtemp()
        output_path = os.path.join(output_tmpdir, f"step_unfold_{uuid.uuid4()}.svg")

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
            except OSError as e:
                print(f"[CLEANUP] Warning: Failed to remove {svg_path}: {e}")

            # 面番号データを含める場合
            if return_face_numbers:
                face_numbers = step_unfold_generator.get_face_numbers()
                response_data["face_numbers"] = face_numbers

            success = True
            return response_data
        else:
            # SVGファイルレスポンス
            # ページモードでも単一ファイルに全ページが含まれる
            cleanup_in_background = True
            background_tasks.add_task(cleanup_temp_dir, tmpdir, "tmpdir")
            background_tasks.add_task(cleanup_temp_dir, output_tmpdir, "output_tmpdir")
            success = True
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
    finally:
        # BackgroundTasksを使わない場合は即時クリーンアップする
        if not cleanup_in_background or not success:
            cleanup_temp_dir(tmpdir, label="tmpdir")
            cleanup_temp_dir(output_tmpdir, label="output_tmpdir")


# --- STEP → PDF 展開図エンドポイント ---
@router.post(
    "/api/step/unfold-pdf",
    summary="STEP → PDF Unfold",
    tags=["STEP Processing"],
    responses={
        200: {
            "description": "PDF file with paginated papercraft template",
            "content": {
                "application/pdf": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "PDF file with multi-page unfold layout"
                }
            }
        },
        400: {"description": "Invalid file format, empty file, or canvas mode not supported for PDF"},
        503: {"description": "OpenCASCADE not available"}
    }
)
async def unfold_step_to_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="STEP file (.step/.stp)"),
    layout_mode: str = Form("paged", description="レイアウトモード / Layout mode (only 'paged' supported for PDF)"),
    page_format: str = Form("A4", description="ページフォーマット / Page format (A4/A3/Letter)"),
    page_orientation: str = Form("portrait", description="ページ方向 / Page orientation (portrait=縦, landscape=横)"),
    scale_factor: float = Form(150.0, description="縮尺倍率 / Scale factor (e.g., 150 = 1:150 scale)"),
    texture_mappings: Optional[str] = Form(None, description="テクスチャマッピング情報（JSON配列） / Texture mappings as JSON array"),
    mirror_horizontal: bool = Form(False, description="左右反転モード / Mirror horizontally")
):
    """
    STEPファイル（.step/.stp）を受け取り、展開図をPDF形式で生成するAPI。

    Unfold 3D STEP file to multi-page PDF papercraft template.

    **レイアウトモード / Layout Modes**:
    - `paged`: ページ分割（A4/A3/Letterサイズに自動配置） / Paginated layout (only mode supported for PDF)
    - `canvas`: ❌ Not supported for PDF export (use SVG endpoint for canvas mode)

    **出力形式 / Output Format**:
    - PDF file with multiple pages (one page per sheet)
    - Each page includes fold/cut lines, assembly tabs, and scale bars
    - Custom headers: X-Layout-Mode, X-Page-Format, X-Page-Orientation, X-Page-Count, X-Scale-Factor

    **テクスチャマッピング / Texture Mappings**:
    - JSON array: `[{"faceNumber": 1, "patternId": "brick", "tileCount": 5}, ...]`
    - Overlays SVG patterns on specific faces for realistic papercraft appearance
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。")

    tmpdir = None
    result_path = None  # PDFが正常に生成されたかを追跡
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
            raise HTTPException(status_code=400, detail="STEPファイル（.step/.stp）のみ対応です。")

        # 一時ディレクトリ作成
        file_ext = "step" if file.filename.lower().endswith('.step') else "stp"
        tmpdir, in_path, total = await save_upload_to_tmpdir(file, file_ext)

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
            scale_factor=scale_factor,
            mirror_horizontal=mirror_horizontal
        )

        # テクスチャマッピングを設定
        if parsed_texture_mappings:
            generator.set_texture_mappings(parsed_texture_mappings)

        # SVGエンドポイントと同じパイプラインを実行（max_faces=20を使用）
        # 1. BREPトポロジ解析
        generator.analyze_brep_topology()

        # 2. パラメータ設定（全パラメータを漏れなく設定）
        generator.scale_factor = request.scale_factor
        generator.units = request.units
        generator.tab_width = request.tab_width
        generator.show_scale = request.show_scale
        generator.show_fold_lines = request.show_fold_lines
        generator.show_cut_lines = request.show_cut_lines
        generator.layout_mode = request.layout_mode
        generator.page_format = request.page_format
        generator.page_orientation = request.page_orientation
        generator.mirror_horizontal = request.mirror_horizontal

        # SVGエクスポーターとレイアウトマネージャーにも設定を反映（重要！）
        generator.svg_exporter.scale_factor = request.scale_factor
        generator.svg_exporter.units = request.units
        generator.svg_exporter.tab_width = request.tab_width
        generator.svg_exporter.show_scale = request.show_scale
        generator.svg_exporter.show_fold_lines = request.show_fold_lines
        generator.svg_exporter.show_cut_lines = request.show_cut_lines
        generator.svg_exporter.layout_mode = request.layout_mode
        generator.svg_exporter.page_format = request.page_format
        generator.svg_exporter.page_orientation = request.page_orientation
        generator.svg_exporter.mirror_horizontal = request.mirror_horizontal
        generator.layout_manager.scale_factor = request.scale_factor
        generator.layout_manager.page_format = request.page_format
        generator.layout_manager.page_orientation = request.page_orientation

        # パラメータ設定完了のログ出力
        print(f"[PDF] Parameters set:")
        print(f"  scale_factor: {request.scale_factor}")
        print(f"  units: {request.units}")
        print(f"  tab_width: {request.tab_width}")
        print(f"  show_scale: {request.show_scale}")
        print(f"  show_fold_lines: {request.show_fold_lines}")
        print(f"  show_cut_lines: {request.show_cut_lines}")
        print(f"  layout_mode: {request.layout_mode}")
        print(f"  page_format: {request.page_format}")
        print(f"  page_orientation: {request.page_orientation}")
        print(f"  mirror_horizontal: {request.mirror_horizontal}")

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

            # PDFファイルを返す（レスポンス送信後にtmpdirをクリーンアップ）
            background_tasks.add_task(cleanup_temp_dir, tmpdir, "tmpdir")
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
    finally:
        # エラー時のみ即座にクリーンアップ（正常時はBackgroundTasksでクリーンアップ）
        if result_path is None:
            cleanup_temp_dir(tmpdir, label="tmpdir")
