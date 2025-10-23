"""
PDF Export for BREP Papercraft Unfolding

This module handles the conversion of SVG unfold diagrams to PDF format.
It provides functionality for:
- Converting individual SVG pages to PDF pages
- Merging multiple SVG files into a single multi-page PDF
- Maintaining accurate page sizes (A4, A3, Letter)
- Preserving scale and layout from the original SVG
"""

import os
import tempfile
from typing import List, Dict, Optional
import logging

# PDF generation library - try multiple backends for compatibility
try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False
    logging.warning("cairosvg not available. PDF export will use fallback method.")

try:
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.pagesizes import A4, A3, letter
    from reportlab.lib.utils import ImageReader
    from svglib.svglib import renderSVG
    from reportlab.graphics import renderPDF
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("reportlab/svglib not available.")

try:
    from PyPDF2 import PdfWriter, PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    try:
        from pypdf import PdfWriter, PdfReader
        PYPDF2_AVAILABLE = True
    except ImportError:
        PYPDF2_AVAILABLE = False
        logging.warning("PyPDF2/pypdf not available. Multi-page PDF merging may not work.")


class PDFExporter:
    """
    PDF出力を専門とする独立したクラス。
    SVG形式の展開図をPDF形式に変換する機能を提供。
    """

    def __init__(self, page_format: str = "A4", page_orientation: str = "portrait"):
        """
        PDFExporterを初期化。

        Args:
            page_format: ページフォーマット (A4, A3, Letter)
            page_orientation: ページ方向 ("portrait" or "landscape")
        """
        self.page_format = page_format
        self.page_orientation = page_orientation

        # ページサイズの定義 (mm単位) - SVGExporterと同じ
        self.page_sizes_mm = {
            "A4": {"width": 210, "height": 297},
            "A3": {"width": 297, "height": 420},
            "Letter": {"width": 216, "height": 279}
        }

        # ReportLabのページサイズ定義（ポイント単位: 1pt = 1/72 inch）
        self.reportlab_page_sizes = {
            "A4": A4,
            "A3": A3,
            "Letter": letter
        }

        # 現在のページサイズを計算
        self._calculate_page_dimensions()

    def _calculate_page_dimensions(self):
        """
        ページ方向を考慮してページ寸法を計算
        """
        base_size = self.page_sizes_mm[self.page_format]

        if self.page_orientation == "landscape":
            # 横向きの場合、幅と高さを入れ替え
            self.page_width_mm = base_size["height"]
            self.page_height_mm = base_size["width"]
        else:
            # 縦向きの場合、そのまま使用
            self.page_width_mm = base_size["width"]
            self.page_height_mm = base_size["height"]

    def export_svg_list_to_pdf(self, svg_paths: List[str], output_path: str) -> str:
        """
        複数のSVGファイルを1つのPDFファイルに変換（各SVGが1ページになる）

        Args:
            svg_paths: SVGファイルパスのリスト
            output_path: 出力PDFファイルのパス

        Returns:
            str: 出力されたPDFファイルのパス
        """
        if not svg_paths:
            raise ValueError("SVGファイルパスのリストが空です")

        print(f"PDFExporter: {len(svg_paths)}個のSVGファイルをPDFに変換中...")

        if CAIROSVG_AVAILABLE:
            return self._export_with_cairosvg(svg_paths, output_path)
        elif REPORTLAB_AVAILABLE and PYPDF2_AVAILABLE:
            return self._export_with_reportlab(svg_paths, output_path)
        else:
            raise RuntimeError(
                "PDF生成に必要なライブラリがインストールされていません。"
                "cairosvg または (reportlab + svglib + PyPDF2) をインストールしてください。"
            )

    def _export_with_cairosvg(self, svg_paths: List[str], output_path: str) -> str:
        """
        cairosvgを使用してSVG → PDF変換

        Args:
            svg_paths: SVGファイルパスのリスト
            output_path: 出力PDFファイルのパス

        Returns:
            str: 出力されたPDFファイルのパス
        """
        print("PDFExporter: cairosvgを使用してPDF生成中...")

        if len(svg_paths) == 1:
            # 単一ページの場合は直接変換
            with open(svg_paths[0], 'rb') as svg_file:
                svg_data = svg_file.read()

            cairosvg.svg2pdf(
                bytestring=svg_data,
                write_to=output_path
            )

            print(f"PDFExporter: 単一ページPDFを生成: {output_path}")
            return output_path

        else:
            # 複数ページの場合、各SVGを個別にPDFに変換してからマージ
            temp_pdfs = []
            temp_dir = tempfile.mkdtemp()

            try:
                # 各SVGをPDFに変換
                for i, svg_path in enumerate(svg_paths):
                    temp_pdf_path = os.path.join(temp_dir, f"page_{i:03d}.pdf")

                    with open(svg_path, 'rb') as svg_file:
                        svg_data = svg_file.read()

                    cairosvg.svg2pdf(
                        bytestring=svg_data,
                        write_to=temp_pdf_path
                    )

                    temp_pdfs.append(temp_pdf_path)
                    print(f"PDFExporter: ページ {i+1}/{len(svg_paths)} を変換")

                # PDFをマージ
                if PYPDF2_AVAILABLE:
                    self._merge_pdfs(temp_pdfs, output_path)
                    print(f"PDFExporter: {len(temp_pdfs)}ページのPDFをマージ: {output_path}")
                else:
                    # PyPDF2が利用できない場合は最初のPDFのみを返す
                    import shutil
                    shutil.copy(temp_pdfs[0], output_path)
                    print(f"警告: PyPDF2が利用できないため、最初のページのみを出力しました")

                return output_path

            finally:
                # 一時ファイルをクリーンアップ
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

    def _export_with_reportlab(self, svg_paths: List[str], output_path: str) -> str:
        """
        reportlab + svglibを使用してSVG → PDF変換

        Args:
            svg_paths: SVGファイルパスのリスト
            output_path: 出力PDFファイルのパス

        Returns:
            str: 出力されたPDFファイルのパス
        """
        print("PDFExporter: reportlab + svglibを使用してPDF生成中...")

        # ページサイズを取得
        if self.page_orientation == "landscape":
            page_size = (self.reportlab_page_sizes[self.page_format][1],
                        self.reportlab_page_sizes[self.page_format][0])
        else:
            page_size = self.reportlab_page_sizes[self.page_format]

        # 各SVGを個別にPDFに変換してからマージ
        temp_pdfs = []
        temp_dir = tempfile.mkdtemp()

        try:
            for i, svg_path in enumerate(svg_paths):
                temp_pdf_path = os.path.join(temp_dir, f"page_{i:03d}.pdf")

                # SVGをReportLabのDrawingオブジェクトに変換
                drawing = renderSVG.svg2rlg(svg_path)

                if drawing:
                    # DrawingをPDFに変換
                    renderPDF.drawToFile(drawing, temp_pdf_path,
                                        fmt='PDF',
                                        showBoundary=False)
                    temp_pdfs.append(temp_pdf_path)
                    print(f"PDFExporter: ページ {i+1}/{len(svg_paths)} を変換")
                else:
                    print(f"警告: {svg_path} をReportLab Drawingに変換できませんでした")

            # PDFをマージ
            if temp_pdfs:
                if PYPDF2_AVAILABLE:
                    self._merge_pdfs(temp_pdfs, output_path)
                    print(f"PDFExporter: {len(temp_pdfs)}ページのPDFをマージ: {output_path}")
                else:
                    # PyPDF2が利用できない場合は最初のPDFのみを返す
                    import shutil
                    shutil.copy(temp_pdfs[0], output_path)
                    print(f"警告: PyPDF2が利用できないため、最初のページのみを出力しました")
            else:
                raise RuntimeError("PDFページを1つも生成できませんでした")

            return output_path

        finally:
            # 一時ファイルをクリーンアップ
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _merge_pdfs(self, pdf_paths: List[str], output_path: str):
        """
        複数のPDFファイルを1つにマージ

        Args:
            pdf_paths: PDFファイルパスのリスト
            output_path: 出力PDFファイルのパス
        """
        if not PYPDF2_AVAILABLE:
            raise RuntimeError("PyPDF2/pypdfがインストールされていません")

        merger = PdfWriter()

        for pdf_path in pdf_paths:
            with open(pdf_path, 'rb') as pdf_file:
                reader = PdfReader(pdf_file)
                for page in reader.pages:
                    merger.add_page(page)

        with open(output_path, 'wb') as output_file:
            merger.write(output_file)

    def export_single_svg_to_pdf(self, svg_path: str, output_path: str) -> str:
        """
        単一のSVGファイルをPDFファイルに変換

        Args:
            svg_path: SVGファイルのパス
            output_path: 出力PDFファイルのパス

        Returns:
            str: 出力されたPDFファイルのパス
        """
        return self.export_svg_list_to_pdf([svg_path], output_path)

    def update_settings(self, page_format: Optional[str] = None,
                       page_orientation: Optional[str] = None):
        """
        設定を更新する

        Args:
            page_format: ページフォーマット
            page_orientation: ページ方向
        """
        if page_format is not None:
            self.page_format = page_format
        if page_orientation is not None:
            self.page_orientation = page_orientation
        self._calculate_page_dimensions()
