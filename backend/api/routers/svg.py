import os
import tempfile
import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from api.helpers import cleanup_temp_dir
from config import SVG_UPLOAD_LIMITS
from core.pdf_exporter import PDFExporter

router = APIRouter()

MAX_SVG_FILES = SVG_UPLOAD_LIMITS["max_files"]
MAX_SVG_FILE_SIZE_BYTES = SVG_UPLOAD_LIMITS["max_file_size_bytes"]
MAX_SVG_TOTAL_BYTES = SVG_UPLOAD_LIMITS["max_total_bytes"]
SVG_READ_CHUNK_SIZE = 1024 * 1024
SVG_SCAN_BUFFER_BYTES = 64
FORBIDDEN_SVG_TOKENS = (b"<!doctype", b"<!entity")


@router.post(
    "/api/svg/to-pdf",
    summary="SVG → PDF",
    tags=["SVG Processing"],
    responses={
        200: {
            "description": "PDF file generated from SVG pages",
            "content": {
                "application/pdf": {
                    "schema": {"type": "string", "format": "binary"},
                    "example": "PDF file generated from SVG pages"
                }
            }
        },
        400: {"description": "Invalid SVG input or parameters"},
        500: {"description": "PDF export failed"}
    }
)
async def convert_svg_to_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="SVG files (multiple pages allowed)"),
    page_format: str = Form("A4", description="ページフォーマット / Page format (A4/A3/Letter)"),
    page_orientation: str = Form("portrait", description="ページ向き / Page orientation (portrait/landscape)")
):
    """
    SVGファイルをPDF形式に変換するAPI。

    Convert SVG pages to a multi-page PDF.
    """
    tmpdir = None
    cleanup_in_background = False
    success = False

    try:
        if not files:
            raise HTTPException(status_code=400, detail="SVGファイルが指定されていません。")
        if len(files) > MAX_SVG_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"SVGファイル数は最大{MAX_SVG_FILES}件までです。"
            )

        if page_format not in {"A4", "A3", "Letter"}:
            raise HTTPException(status_code=400, detail="page_formatはA4/A3/Letterのみ対応しています。")
        if page_orientation not in {"portrait", "landscape"}:
            raise HTTPException(status_code=400, detail="page_orientationはportrait/landscapeのみ対応しています。")

        tmpdir = tempfile.mkdtemp()
        svg_paths: List[str] = []

        total_bytes = 0
        for index, upload in enumerate(files, 1):
            filename = upload.filename or f"page_{index}.svg"
            if not filename.lower().endswith(".svg"):
                raise HTTPException(status_code=400, detail="SVGファイルのみ対応です。")

            output_path = os.path.join(tmpdir, f"page_{index:03d}.svg")
            file_total = 0
            scan_tail = b""
            with open(output_path, "wb") as dst:
                while True:
                    chunk = await upload.read(SVG_READ_CHUNK_SIZE)
                    if not chunk:
                        break
                    scan_window = (scan_tail + chunk).lower()
                    if any(token in scan_window for token in FORBIDDEN_SVG_TOKENS):
                        raise HTTPException(
                            status_code=400,
                            detail="SVGに危険なXML宣言が含まれているため処理できません。"
                        )
                    scan_tail = scan_window[-SVG_SCAN_BUFFER_BYTES:]
                    chunk_size = len(chunk)
                    file_total += chunk_size
                    total_bytes += chunk_size
                    if file_total > MAX_SVG_FILE_SIZE_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail=f"SVGファイルのサイズは{MAX_SVG_FILE_SIZE_BYTES // (1024 * 1024)}MBまでです。"
                        )
                    if total_bytes > MAX_SVG_TOTAL_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail=f"SVGファイルの合計サイズは{MAX_SVG_TOTAL_BYTES // (1024 * 1024)}MBまでです。"
                        )
                    dst.write(chunk)

            if file_total == 0:
                raise HTTPException(status_code=400, detail="アップロードされたファイルが空です。")

            svg_paths.append(output_path)

        pdf_path = os.path.join(tmpdir, f"svg_to_pdf_{uuid.uuid4()}.pdf")
        pdf_exporter = PDFExporter(page_format=page_format, page_orientation=page_orientation)
        result_path = pdf_exporter.export_svg_list_to_pdf(svg_paths, pdf_path)

        cleanup_in_background = True
        background_tasks.add_task(cleanup_temp_dir, tmpdir, "tmpdir")
        success = True
        return FileResponse(
            path=result_path,
            media_type="application/pdf",
            filename=f"svg_to_pdf_{page_format}_{page_orientation}_{uuid.uuid4()}.pdf",
            headers={
                "X-Page-Format": page_format,
                "X-Page-Orientation": page_orientation,
                "X-Page-Count": str(len(svg_paths))
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"SVG→PDFエクスポートエラー: {str(e)}")
    finally:
        if not cleanup_in_background or not success:
            cleanup_temp_dir(tmpdir, label="tmpdir")
