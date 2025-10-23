import os
import tempfile
import uuid
import base64
import json
import math
import time
from typing import List, Optional, Dict, Any, Union, Tuple
import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.distance import cdist
import io

from config import OCCT_AVAILABLE
from core.file_loaders import FileLoader
from core.geometry_analyzer import GeometryAnalyzer
from core.unfold_engine import UnfoldEngine
from core.layout_manager import LayoutManager
from core.svg_exporter import SVGExporter
from core.pdf_exporter import PDFExporter

if OCCT_AVAILABLE:
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core import BRepTools
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE
    from OCC.Core.BRepGProp import BRepGProp_Face
    from OCC.Core import BRepGProp
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomLProp import GeomLProp_SLProps
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Edge, TopoDS_Vertex
    from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Pln, gp_Cylinder, gp_Cone, gp_Trsf, gp_Ax1, gp_Ax2, gp_Ax3
    from OCC.Core.Geom import Geom_Surface, Geom_Plane, Geom_CylindricalSurface, Geom_ConicalSurface
    from OCC.Core.Standard import Standard_Failure


class StepUnfoldGenerator:
    """
    STEPソリッドモデルから展開図（SVG）を生成する専用クラス。
    """
    def __init__(self):
        # ═══ 前提条件検証：品質保証の最初の砦 ═══
        if not OCCT_AVAILABLE:
            raise RuntimeError(
                "OpenCASCADE Technology が利用できません。\n" +
                "商用グレードBREP処理には OCCT が必須です。\n" +
                "インストール手順：\n" +
                "2. conda install -c conda-forge python-opencascade"
            )
        
        # ═══ 幾何学的状態管理：BREPデータの構造化記憶域 ═══
        self.solid_shape = None  # ソリッドシェイプを格納
        # 読み込まれたBREPソリッド：すべての幾何学情報の根源となる形状データ
        # None状態は「未初期化」を意味し、処理前の安全な初期状態
        
        # ファイル読み込み処理クラス
        self.file_loader = FileLoader()
        
        # ファイル情報の同期用
        self.last_file_info = None
        
        # 幾何学解析クラス
        self.geometry_analyzer = GeometryAnalyzer()
        
        # 解析済みデータへの参照
        self.faces_data = self.geometry_analyzer.faces_data
        self.edges_data = self.geometry_analyzer.edges_data
        
        # 展開エンジン
        self.unfold_engine = UnfoldEngine()
        
        self.unfold_groups: List[List[int]] = []
        # 展開グループリスト：展開可能な面をグループ化した結果を保存
        
        # ═══ 設定パラメータ：ユーザー要求の内部表現 ═══
        self.scale_factor = 10.0    # スケール倍率：デジタル-物理変換比率（より大きな初期値）
        
        # レイアウトマネージャー
        self.layout_manager = LayoutManager(scale_factor=self.scale_factor)
        self.layout_mode = "canvas"  # デフォルトはフリーキャンバスモード
        self.page_format = "A4"
        self.page_orientation = "portrait"
        self.units = "mm"           # 単位系：寸法の解釈基準
        self.tab_width = 5.0        # タブ幅：接着部の物理的寸法
        self.show_scale = True      # スケールバー：図面標準への準拠
        self.show_fold_lines = True # 折り線：組み立て指示の視覚化
        self.show_cut_lines = True  # 切断線：加工指示の視覚化
        
        # SVGエクスポーター
        self.svg_exporter = SVGExporter(
            scale_factor=self.scale_factor,
            units=self.units,
            tab_width=self.tab_width,
            show_scale=self.show_scale,
            show_fold_lines=self.show_fold_lines,
            show_cut_lines=self.show_cut_lines,
            layout_mode=self.layout_mode,
            page_format=self.page_format,
            page_orientation=self.page_orientation
        )
        
        # ═══ 処理統計情報：品質管理と性能監視のためのメトリクス ═══
        self.stats = {
            "total_faces": 0,        # 総面数：入力モデルの複雑さ指標
            "planar_faces": 0,       # 平面数：直接展開可能な面の数
            "cylindrical_faces": 0,  # 円筒面数：円筒展開対象面の数
            "conical_faces": 0,      # 円錐面数：円錐展開対象面の数
            "other_faces": 0,        # その他面数：特殊処理が必要な面の数
            "unfoldable_faces": 0,   # 展開可能面数：最終的に展開された面の数
            "processing_time": 0.0   # 処理時間：性能評価指標（秒単位）
        }

        # ═══ テクスチャマッピング：面番号とテクスチャパターンの対応表 ═══
        self.texture_mappings: List[Dict[str, Any]] = []
        # [{faceNumber: int, patternId: str, tileCount: int}, ...]

        # ═══ 展開ネット生成モード：隣接する面を繋げて展開図を生成 ═══
        # 注意: 現在の実装は簡易版のため、正確な展開ネットを生成できません
        # 各面を個別に展開する方が正確です
        self.generate_unfolding_net = False  # デフォルトで展開ネットモードを無効化


    def set_texture_mappings(self, texture_mappings: List[Dict[str, Any]]):
        """
        テクスチャマッピング情報を設定する。

        Args:
            texture_mappings: [{faceNumber: int, patternId: str, tileCount: int}, ...]
        """
        self.texture_mappings = texture_mappings
        print(f"[StepUnfoldGenerator] Set {len(texture_mappings)} texture mappings")

    def load_from_file(self, file_path: str) -> bool:
        """
        ファイル拡張子に応じて適切な読み込み関数を呼び出す。
        """
        # FileLoaderクラスのload_from_fileメソッドを使用
        result = self.file_loader.load_from_file(file_path)
        # 読み込んだ形状を自分のインスタンスに設定
        self.solid_shape = self.file_loader.solid_shape
        return result

    def diagnose_file(self, file_path: str, save_debug_copy: bool = True) -> dict:
        """
        ファイルの基本情報を診断し、デバッグ情報を返す。
        save_debug_copyがTrueの場合、デバッグ用にファイルのコピーを保存する。
        """
        return self.file_loader.diagnose_file(file_path, save_debug_copy)

    def load_from_bytes(self, file_content: bytes, file_ext: str) -> bool:
        """
        バイト列からCADデータを読み込む（API経由アップロード対応）。
        """
        result = self.file_loader.load_from_bytes(file_content, file_ext)
        # 読み込んだ形状を自分のインスタンスに設定
        self.solid_shape = self.file_loader.solid_shape
        # last_file_infoを同期
        self.last_file_info = self.file_loader.last_file_info
        return result
    
    def load_brep_from_bytes(self, file_content: bytes) -> bool:
        """
        バイト列からBREPデータを読み込む（API経由アップロード対応）。
        無効なBREPの場合は、パラメータから立方体を生成する。
        """
        result = self.file_loader.load_brep_from_bytes(file_content)
        # 読み込んだ形状を自分のインスタンスに設定
        self.solid_shape = self.file_loader.solid_shape
        # last_file_infoを同期
        self.last_file_info = self.file_loader.last_file_info
        return result

    def analyze_brep_topology(self):
        """
        BREPソリッドのトポロジ構造を詳細解析。
        面・エッジ・頂点の幾何特性を抽出し、展開戦略を決定。
        """
        if self.solid_shape is None:
            raise ValueError("BREPデータが読み込まれていません")
        
        # 幾何学解析クラスに委譲
        self.geometry_analyzer.analyze_brep_topology(self.solid_shape)
        
        # 統計情報更新
        self.stats["total_faces"] = self.geometry_analyzer.stats["total_faces"]
        self.stats["planar_faces"] = self.geometry_analyzer.stats["planar_faces"]
        self.stats["cylindrical_faces"] = self.geometry_analyzer.stats["cylindrical_faces"]
        self.stats["conical_faces"] = self.geometry_analyzer.stats["conical_faces"]
        self.stats["other_faces"] = self.geometry_analyzer.stats["other_faces"]
        
        # 展開エンジンに幾何学データを設定
        self.unfold_engine.set_geometry_data(self.faces_data, self.edges_data)

    def group_faces_for_unfolding(self, max_faces: int = 20) -> List[List[int]]:
        """
        展開可能な面をグループ化。
        展開エンジンに処理を委譲。
        """
        # 展開エンジンの設定を更新
        self.unfold_engine.scale_factor = self.scale_factor
        self.unfold_engine.tab_width = self.tab_width

        # 展開エンジンに処理を委譲
        self.unfold_groups = self.unfold_engine.group_faces_for_unfolding(
            max_faces=max_faces,
            generate_unfolding_net=self.generate_unfolding_net
        )
        return self.unfold_groups

    def unfold_face_groups(self) -> List[Dict]:
        """
        各面グループを2D展開図に変換。
        展開エンジンに処理を委譲。
        """
        # 展開エンジンの設定を更新
        self.unfold_engine.scale_factor = self.scale_factor
        self.unfold_engine.tab_width = self.tab_width
        
        # 展開エンジンに処理を委譲
        return self.unfold_engine.unfold_face_groups()

    def layout_unfolded_groups(self, unfolded_groups: List[Dict]) -> List[Dict]:
        """
        展開済みグループを紙面上に効率的に配置。
        重複回避・用紙サイズ最適化を実施。
        """
        # レイアウトマネージャーのスケール倍率を更新
        self.layout_manager.update_scale_factor(self.scale_factor)
        
        # レイアウトマネージャーに処理を委譲
        return self.layout_manager.layout_unfolded_groups(unfolded_groups)


    def export_to_svg(self, placed_groups: List[Dict], output_path: str) -> str:
        """
        配置済み展開図をSVG形式で出力。
        SVGExporterクラスに処理を委譲。
        """
        # SVGエクスポーターの設定を更新
        self.svg_exporter.update_settings(
            scale_factor=self.scale_factor,
            units=self.units,
            tab_width=self.tab_width,
            show_scale=self.show_scale,
            show_fold_lines=self.show_fold_lines,
            show_cut_lines=self.show_cut_lines,
            layout_mode=self.layout_mode,
            page_format=self.page_format,
            page_orientation=self.page_orientation
        )

        # テクスチャマッピングを設定
        if self.texture_mappings:
            self.svg_exporter.set_texture_mappings(self.texture_mappings)

        # SVGエクスポーターに処理を委譲
        return self.svg_exporter.export_to_svg(placed_groups, output_path, self.layout_manager)
    
    def export_to_svg_paged_single_file(self, paged_groups: List[List[Dict]], output_path: str) -> str:
        """
        ページ分割された展開図を単一のSVGファイルに出力。
        """
        # SVGエクスポーターの設定を更新
        self.svg_exporter.update_settings(
            scale_factor=self.scale_factor,
            units=self.units,
            tab_width=self.tab_width,
            show_scale=self.show_scale,
            show_fold_lines=self.show_fold_lines,
            show_cut_lines=self.show_cut_lines,
            layout_mode=self.layout_mode,
            page_format=self.page_format,
            page_orientation=self.page_orientation
        )

        # テクスチャマッピングを設定
        if self.texture_mappings:
            self.svg_exporter.set_texture_mappings(self.texture_mappings)

        # SVGエクスポーターに処理を委譲
        return self.svg_exporter.export_to_svg_paged_single_file(paged_groups, output_path)

    def export_to_pdf_paged(self, paged_groups: List[List[Dict]], output_path: str) -> str:
        """
        ページ分割された展開図をPDF形式で出力。

        各ページを個別のSVGファイルとして一時保存し、PDFExporterを使用して
        1つのマルチページPDFファイルに変換する。

        Args:
            paged_groups: ページごとに分割された展開図グループのリスト
            output_path: 出力PDFファイルのパス

        Returns:
            str: 出力されたPDFファイルのパス
        """
        print(f"PDFエクスポート開始: {len(paged_groups)}ページ")

        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp()
        svg_paths = []

        try:
            # SVGエクスポーターの設定を更新
            self.svg_exporter.update_settings(
                scale_factor=self.scale_factor,
                units=self.units,
                tab_width=self.tab_width,
                show_scale=self.show_scale,
                show_fold_lines=self.show_fold_lines,
                show_cut_lines=self.show_cut_lines,
                layout_mode=self.layout_mode,
                page_format=self.page_format,
                page_orientation=self.page_orientation
            )

            # テクスチャマッピングを設定
            if self.texture_mappings:
                self.svg_exporter.set_texture_mappings(self.texture_mappings)

            # 各ページを個別のSVGファイルとして保存
            svg_paths = self.svg_exporter.export_to_svg_paged(paged_groups, temp_dir)

            print(f"SVG生成完了: {len(svg_paths)}ファイル")

            # PDFExporterを初期化
            pdf_exporter = PDFExporter(
                page_format=self.page_format,
                page_orientation=self.page_orientation
            )

            # SVGファイルリストからPDFを生成
            result_path = pdf_exporter.export_svg_list_to_pdf(svg_paths, output_path)

            print(f"PDFエクスポート完了: {result_path}")

            return result_path

        finally:
            # 一時ファイルをクリーンアップ
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"一時ディレクトリを削除: {temp_dir}")



    def generate_brep_papercraft(self, request, output_path: Optional[str] = None) -> Tuple[str, Dict]:
        """
        BREPソリッドから展開図を一括生成。
        商用グレードの完全なワークフロー。
        """
        if self.solid_shape is None:
            raise ValueError("BREPソリッドが読み込まれていません")
        
        if output_path is None:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f"brep_papercraft_{uuid.uuid4()}.svg")
        
        try:
            start_time = time.time()
            
            # パラメータ設定
            self.scale_factor = request.scale_factor
            self.units = request.units
            self.tab_width = request.tab_width
            self.show_scale = request.show_scale
            self.show_fold_lines = request.show_fold_lines
            self.show_cut_lines = request.show_cut_lines
            self.layout_mode = request.layout_mode
            self.page_format = request.page_format
            self.page_orientation = request.page_orientation
            
            # UnfoldEngine、LayoutManager、SVGExporterのscale_factorを更新
            self.unfold_engine.scale_factor = self.scale_factor
            self.unfold_engine.tab_width = self.tab_width
            self.layout_manager.scale_factor = self.scale_factor
            self.svg_exporter.scale_factor = self.scale_factor
            self.svg_exporter.tab_width = self.tab_width
            self.svg_exporter.layout_mode = self.layout_mode
            self.svg_exporter.page_format = self.page_format
            self.svg_exporter.page_orientation = self.page_orientation
            
            # 1. BREPトポロジ解析
            self.analyze_brep_topology()
            
            # 2. 展開可能面のグルーピング
            self.group_faces_for_unfolding(request.max_faces)
            
            # 3. 各グループの2D展開
            unfolded_groups = self.unfold_face_groups()
            
            # 4. レイアウトモードに応じた配置
            if self.layout_mode == "paged":
                # ページモード: ページ単位でレイアウト
                self.layout_manager.update_page_settings(
                    page_format=self.page_format,
                    page_orientation=self.page_orientation
                )
                paged_groups, layout_warnings = self.layout_manager.layout_for_pages(unfolded_groups)

                # 5. 単一SVGファイルに全ページを出力
                svg_path = self.export_to_svg_paged_single_file(paged_groups, output_path)

                # 統計情報にページ数を追加
                self.stats["page_count"] = len(paged_groups)
                self.stats["svg_files"] = [svg_path]  # 単一ファイル
                # 警告情報を追加
                if layout_warnings:
                    self.stats["warnings"] = layout_warnings
            else:
                # キャンバスモード: 従来の単一SVG
                placed_groups = self.layout_unfolded_groups(unfolded_groups)
                
                # 5. SVG出力
                svg_path = self.export_to_svg(placed_groups, output_path)
            
            # 処理統計更新
            end_time = time.time()
            self.stats["processing_time"] = end_time - start_time
            self.stats["unfoldable_faces"] = sum(
                len(group["polygons"]) 
                for page in (paged_groups if self.layout_mode == "paged" else [placed_groups])
                for group in (page if self.layout_mode == "paged" else placed_groups)
            )
            self.stats["layout_mode"] = self.layout_mode
            
            return svg_path, self.stats
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValueError(f"BREP展開図生成エラー: {str(e)}")

    def get_face_numbers(self) -> List[Dict[str, int]]:
        """
        バックエンドで生成された面番号データを取得する。
        フロントエンドとの面番号統一に使用。
        
        Returns:
            List[Dict]: [{"faceIndex": 0, "faceNumber": 1}, ...] 形式の面番号マッピング
        """
        face_numbers = []
        
        if self.faces_data:
            for face_index, face_data in enumerate(self.faces_data):
                face_number = face_data.get("face_number", face_index + 1)
                face_numbers.append({
                    "faceIndex": face_index,
                    "faceNumber": face_number
                })
                
        print(f"StepUnfoldGenerator.get_face_numbers(): {len(face_numbers)}個の面番号データを返します")
        return face_numbers