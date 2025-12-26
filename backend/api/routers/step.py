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
            "description": "SVG/PDF file or JSON response with unfold data",
            "content": {
                "image/svg+xml": {
                    "example": "SVG file content with unfold layout"
                },
                "application/json": {
                    "examples": {
                        "single_svg": {
                            "summary": "Single SVG content",
                            "value": {
                                "svg_content": "<svg>...</svg>",
                                "stats": {"page_count": 3, "total_faces": 42},
                                "face_numbers": [1, 2, 3]
                            }
                        },
                        "paged_svg": {
                            "summary": "Per-page SVGs",
                            "value": {
                                "pages": ["<svg>...</svg>", "<svg>...</svg>"],
                                "stats": {"page_count": 2, "total_faces": 42},
                                "face_numbers": [1, 2, 3]
                            }
                        }
                    }
                },
                "application/pdf": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "PDF file with multi-page unfold layout"
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
    output_format: str = Form("svg", description="出力形式 / Output format (svg/json/svg_pages/pdf)"),
    layout_mode: str = Form("paged", description="レイアウトモード / Layout mode (canvas/paged)"),
    page_format: str = Form("A4", description="ページフォーマット / Page format (A4/A3/Letter)"),
    page_orientation: str = Form("portrait", description="ページ向き / Orientation (portrait/landscape)"),
    scale_factor: float = Form(10.0, description="縮尺倍率 / Scale factor (例: 150=1/150)"),
    texture_mappings: Optional[str] = Form(None, description="テクスチャマッピング情報（JSON） / Texture mappings (JSON)"),
    mirror_horizontal: bool = Form(False, description="左右反転モード / Mirror horizontally")
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
    - `svg_pages`: JSONレスポンス（ページごとのSVG配列） / JSON response with per-page SVGs (paged only)
    - `pdf`: PDFファイル（ページごとのPDF） / PDF file (paged only)

    Args:
        file: STEPファイル / STEP file (.step/.stp)
        return_face_numbers: 面番号データを含む / Include face numbers (default: True)
        output_format: 出力形式 / Output format (svg/json/svg_pages/pdf, default: "svg")
        - svg_pages: JSON with per-page SVGs (paged only)
        - pdf: PDF output (paged only)
        layout_mode: レイアウトモード / Layout mode (canvas/paged, default: "paged")
        page_format: ページフォーマット / Page format (A4/A3/Letter, default: "A4")
        page_orientation: ページ向き / Orientation (portrait/landscape, default: "portrait")
        scale_factor: 縮尺倍率 / Scale factor (例: 150 = 1/150 scale, default: 10.0)
        texture_mappings: テクスチャマッピング情報（JSON） / Texture mappings (JSON array)
        mirror_horizontal: 左右反転モード / Mirror horizontally

    Returns:
        - output_format="svg": SVGファイル / SVG file
        - output_format="json": JSONレスポンス / JSON response with SVG content and statistics
        - output_format="svg_pages": JSONレスポンス / JSON response with per-page SVGs
        - output_format="pdf": PDFファイル / PDF file
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
        output_format_normalized = output_format.lower()
        supported_formats = {"svg", "json", "svg_pages", "pdf"}
        if output_format_normalized not in supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"output_formatは{', '.join(sorted(supported_formats))}のみ対応です。"
            )
        if output_format_normalized in {"svg_pages", "pdf"} and layout_mode != "paged":
            raise HTTPException(
                status_code=400,
                detail="svg_pages/pdfの出力は layout_mode='paged' のみ対応しています。"
            )

        # レイアウトオプションを含むBrepPapercraftRequestを作成
        request = BrepPapercraftRequest(
            layout_mode=layout_mode,
            page_format=page_format,
            page_orientation=page_orientation,
            scale_factor=scale_factor,
            mirror_horizontal=mirror_horizontal
        )

        # テクスチャマッピングを渡す
        if parsed_texture_mappings:
            step_unfold_generator.set_texture_mappings(parsed_texture_mappings)

        if output_format_normalized in {"svg", "json"}:
            output_tmpdir = tempfile.mkdtemp()
            output_path = os.path.join(output_tmpdir, f"step_unfold_{uuid.uuid4()}.svg")
            svg_path, stats = step_unfold_generator.generate_brep_papercraft(request, output_path)

            if output_format_normalized == "json":
                with open(svg_path, 'r', encoding='utf-8') as svg_file:
                    svg_content = svg_file.read()

                response_data = {
                    "svg_content": svg_content,
                    "stats": stats
                }

                if "warnings" in stats and stats["warnings"]:
                    response_data["warnings"] = stats["warnings"]

                try:
                    os.unlink(svg_path)
                except OSError as e:
                    print(f"[CLEANUP] Warning: Failed to remove {svg_path}: {e}")

                if return_face_numbers:
                    face_numbers = step_unfold_generator.get_face_numbers()
                    response_data["face_numbers"] = face_numbers

                success = True
                return response_data

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

        paged_groups, stats = step_unfold_generator.generate_brep_papercraft_pages(request)

        if output_format_normalized == "svg_pages":
            output_tmpdir = tempfile.mkdtemp()
            try:
                svg_paths = step_unfold_generator.export_to_svg_paged_files(paged_groups, output_tmpdir)

                pages = []
                for svg_path in svg_paths:
                    with open(svg_path, 'r', encoding='utf-8') as svg_file:
                        pages.append(svg_file.read())

                response_data = {
                    "pages": pages,
                    "stats": stats
                }

                if "warnings" in stats and stats["warnings"]:
                    response_data["warnings"] = stats["warnings"]

                if return_face_numbers:
                    face_numbers = step_unfold_generator.get_face_numbers()
                    response_data["face_numbers"] = face_numbers

                success = True
                return response_data
            finally:
                cleanup_temp_dir(output_tmpdir, label="output_tmpdir")
                output_tmpdir = None

        output_tmpdir = tempfile.mkdtemp()
        pdf_path = os.path.join(output_tmpdir, f"step_unfold_{uuid.uuid4()}.pdf")
        result_path = step_unfold_generator.export_to_pdf_paged(paged_groups, pdf_path)

        cleanup_in_background = True
        background_tasks.add_task(cleanup_temp_dir, tmpdir, "tmpdir")
        background_tasks.add_task(cleanup_temp_dir, output_tmpdir, "output_tmpdir")
        success = True
        return FileResponse(
            path=result_path,
            media_type="application/pdf",
            filename=f"step_unfold_{page_format}_{page_orientation}_{uuid.uuid4()}.pdf",
            headers={
                "X-Layout-Mode": layout_mode,
                "X-Page-Format": page_format,
                "X-Page-Orientation": page_orientation,
                "X-Page-Count": str(stats.get("page_count", len(paged_groups))),
                "X-Scale-Factor": str(scale_factor)
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

        if layout_mode != "paged":
            raise HTTPException(
                status_code=400,
                detail="PDF出力は現在 layout_mode='paged' のみサポートしています。"
            )

        paged_groups, stats = generator.generate_brep_papercraft_pages(request)
        pdf_path = os.path.join(tmpdir, f"unfold_{uuid.uuid4()}.pdf")
        result_path = generator.export_to_pdf_paged(paged_groups, pdf_path)

        print(f"[PDF] Generated PDF with {len(paged_groups)} pages: {result_path}")

        background_tasks.add_task(cleanup_temp_dir, tmpdir, "tmpdir")
        return FileResponse(
            path=result_path,
            media_type="application/pdf",
            filename=f"step_unfold_{page_format}_{page_orientation}_{uuid.uuid4()}.pdf",
            headers={
                "X-Layout-Mode": layout_mode,
                "X-Page-Format": page_format,
                "X-Page-Orientation": page_orientation,
                "X-Page-Count": str(stats.get("page_count", len(paged_groups))),
                "X-Scale-Factor": str(scale_factor)
            }
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
