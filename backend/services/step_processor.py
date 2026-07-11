import os
import tempfile
import uuid
import base64
import json
import time
import hashlib
import copy
from collections import OrderedDict
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
from models.request_models import BrepPapercraftRequest
from utils.logger import get_logger

logger = get_logger(__name__)


def _point_triangle_distance(point: np.ndarray, triangle: np.ndarray) -> float:
    """Return the shortest distance from a point to a 3D triangle."""
    a, b, c = triangle
    ab, ac, ap = b - a, c - a, point - a
    d1, d2 = np.dot(ab, ap), np.dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return float(np.linalg.norm(ap))
    bp = point - b
    d3, d4 = np.dot(ab, bp), np.dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return float(np.linalg.norm(bp))
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        projection = a + (d1 / (d1 - d3)) * ab
        return float(np.linalg.norm(point - projection))
    cp = point - c
    d5, d6 = np.dot(ab, cp), np.dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return float(np.linalg.norm(cp))
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        projection = a + (d2 / (d2 - d6)) * ac
        return float(np.linalg.norm(point - projection))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        edge = c - b
        projection = b + ((d4 - d3) / ((d4 - d3) + (d5 - d6))) * edge
        return float(np.linalg.norm(point - projection))
    denominator = 1.0 / (va + vb + vc)
    projection = a + (vb * denominator) * ab + (vc * denominator) * ac
    return float(np.linalg.norm(point - projection))


def _source_triangles(source: Dict[str, Any]) -> np.ndarray:
    positions = np.asarray(source.get("meshPositions", []), dtype=float)
    if positions.size < 9 or positions.size % 3 != 0:
        return np.empty((0, 3, 3), dtype=float)
    vertices = positions.reshape((-1, 3))
    indices = np.asarray(source.get("meshIndices", []), dtype=int)
    if indices.size >= 3 and indices.size % 3 == 0 and int(indices.max()) < len(vertices):
        return vertices[indices.reshape((-1, 3))]
    triangle_vertex_count = (len(vertices) // 3) * 3
    return vertices[:triangle_vertex_count].reshape((-1, 3, 3))


def _curved_face_sample_points(face: Dict[str, Any], max_points: int = 32) -> np.ndarray:
    """Return distributed boundary points that are known to lie on a curved face."""
    if face.get("surface_type") == "plane":
        return np.empty((0, 3), dtype=float)

    points = []
    for boundary in face.get("boundary_curves", []):
        for point in boundary:
            if len(point) >= 3:
                values = np.asarray(point[:3], dtype=float)
                if np.all(np.isfinite(values)):
                    points.append(values)
    if not points:
        return np.empty((0, 3), dtype=float)

    unique_points = np.unique(np.round(np.asarray(points), decimals=9), axis=0)
    if len(unique_points) <= max_points:
        return unique_points
    sample_indices = np.linspace(0, len(unique_points) - 1, max_points, dtype=int)
    return unique_points[sample_indices]


def _face_to_source_surface_distance(
    face_center: np.ndarray,
    curved_samples: np.ndarray,
    triangles: np.ndarray,
    fallback_distance: float,
) -> float:
    if len(triangles) == 0:
        return fallback_distance
    if len(curved_samples) == 0:
        return min(_point_triangle_distance(face_center, triangle) for triangle in triangles)

    sample_distances = [
        min(_point_triangle_distance(point, triangle) for triangle in triangles)
        for point in curved_samples
    ]
    # A high percentile rejects an adjacent face that only shares one boundary edge.
    return float(np.percentile(sample_distances, 75.0))


def match_source_face_descriptors(
    faces_data: List[Dict[str, Any]],
    source_descriptors: List[Dict[str, Any]],
) -> Tuple[List[Tuple[int, int]], List[int]]:
    """Match every imported STEP face to a source face, allowing one-to-many splits."""
    if not faces_data or not source_descriptors:
        return [], list(range(len(faces_data)))

    face_centers = np.asarray(
        [face.get("match_centroid", face.get("centroid", [0.0, 0.0, 0.0])) for face in faces_data],
        dtype=float,
    )
    source_centers = np.asarray([item["centroid"] for item in source_descriptors], dtype=float)
    all_centers = np.vstack((face_centers, source_centers))
    diagonal = float(np.linalg.norm(np.ptp(all_centers, axis=0)))
    distance_scale = max(diagonal, 1.0)

    source_triangles = [_source_triangles(source) for source in source_descriptors]
    curved_face_samples = [_curved_face_sample_points(face) for face in faces_data]
    matches: List[Tuple[int, int]] = []
    unmatched_faces: List[int] = []
    for face_index, face in enumerate(faces_data):
        face_area = float(face.get("area", 0.0) or 0.0)
        face_normal = face.get("normal_vector")
        best_source_index = None
        best_cost = float("inf")
        best_surface_distance = float("inf")
        for source_index, source in enumerate(source_descriptors):
            center_distance = float(
                np.linalg.norm(face_centers[face_index] - source_centers[source_index])
            )
            source_area = float(source.get("area", 0.0) or 0.0)
            area_excess = max(0.0, face_area / max(source_area, 1e-9) - 1.0)
            normal_error = 0.5
            source_normal = source.get("normal")
            if face_normal and source_normal:
                left = np.asarray(face_normal, dtype=float)
                right = np.asarray(source_normal, dtype=float)
                denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
                if denominator > 1e-12:
                    normal_error = 1.0 - abs(float(np.dot(left, right)) / denominator)
            triangles = source_triangles[source_index]
            surface_distance = _face_to_source_surface_distance(
                face_centers[face_index],
                curved_face_samples[face_index],
                triangles,
                center_distance,
            )
            bounds = source.get("bounds") or {}
            minimum = np.asarray(bounds.get("min", source_centers[source_index]), dtype=float)
            maximum = np.asarray(bounds.get("max", source_centers[source_index]), dtype=float)
            outside = np.maximum(np.maximum(minimum - face_centers[face_index], 0.0), face_centers[face_index] - maximum)
            bounds_distance = float(np.linalg.norm(outside))
            source_order = int(source.get("faceNumber", source_index + 1)) - 1
            cost = (
                0.60 * surface_distance / distance_scale
                + 0.20 * bounds_distance / distance_scale
                + 0.15 * normal_error
                + 0.05 * min(area_excess, 10.0)
                + 1e-10 * abs(face_index - source_order)
            )
            if cost < best_cost:
                best_cost = cost
                best_source_index = source_index
                best_surface_distance = surface_distance

        tolerance_ratio = 0.01 if len(curved_face_samples[face_index]) > 0 else 0.002
        tolerance = max(distance_scale * tolerance_ratio, 1e-4)
        if best_source_index is not None and best_surface_distance <= tolerance:
            matches.append((face_index, best_source_index))
        else:
            unmatched_faces.append(face_index)

    return matches, unmatched_faces

if OCCT_AVAILABLE:
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core import BRepTools
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE
    from OCC.Core.BRepGProp import BRepGProp_Face
    from OCC.Core import BRepGProp
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomLProp import GeomLProp_SLProps
    from OCC.Core.GeomAbs import (
        GeomAbs_Plane,
        GeomAbs_Cylinder,
        GeomAbs_Cone,
        GeomAbs_Sphere,
    )
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Edge, TopoDS_Vertex
    from OCC.Core.gp import (
        gp_Pnt,
        gp_Vec,
        gp_Dir,
        gp_Pln,
        gp_Cylinder,
        gp_Cone,
        gp_Trsf,
        gp_Ax1,
        gp_Ax2,
        gp_Ax3,
    )
    from OCC.Core.Geom import (
        Geom_Surface,
        Geom_Plane,
        Geom_CylindricalSurface,
        Geom_ConicalSurface,
    )
    from OCC.Core.Standard import Standard_Failure


class StepUnfoldGenerator:
    """
    STEPソリッドモデルから展開図（SVG）を生成する専用クラス。
    """

    # クラスレベルの解析結果キャッシュ（LRU、最大10エントリ）
    # キー: SHA256ハッシュ, 値: (faces_data, edges_data, adjacency_map, stats)
    _analysis_cache: OrderedDict = OrderedDict()
    _CACHE_MAX_SIZE = 10

    def __init__(self):
        # ═══ 前提条件検証：品質保証の最初の砦 ═══
        if not OCCT_AVAILABLE:
            raise RuntimeError(
                "OpenCASCADE Technology が利用できません。\n"
                + "商用グレードBREP処理には OCCT が必須です。\n"
                + "インストール手順：\n"
                + "2. conda install -c conda-forge python-opencascade"
            )

        # ═══ 幾何学的状態管理：BREPデータの構造化記憶域 ═══
        self.solid_shape = None  # ソリッドシェイプを格納
        # 読み込まれたBREPソリッド：すべての幾何学情報の根源となる形状データ
        # None状態は「未初期化」を意味し、処理前の安全な初期状態

        # ファイルハッシュ（キャッシュキー用）
        self._file_hash: Optional[str] = None
        self._analysis_ready = False

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
        self.scale_factor = (
            10.0  # スケール倍率：デジタル-物理変換比率（より大きな初期値）
        )
        self._face_match_warnings: List[Dict[str, Any]] = []
        self._source_face_descriptors: List[Dict[str, Any]] = []
        self._exported_face_number_map: Optional[Dict[int, int]] = None

        # レイアウトマネージャー
        self.layout_manager = LayoutManager(scale_factor=self.scale_factor)
        self.layout_mode = "canvas"  # デフォルトはフリーキャンバスモード
        self.page_format = "A4"
        self.page_orientation = "portrait"
        self.scale_mode = "fixed"
        self.applied_scale_factor = self.scale_factor
        self.units = "mm"  # 単位系：寸法の解釈基準
        self.tab_width = 0.0  # タブ幅：0の場合は接着タブを生成しない
        self.show_scale = True  # スケールバー：図面標準への準拠
        self.show_fold_lines = True  # 折り線：組み立て指示の視覚化
        self.show_cut_lines = True  # 切断線：加工指示の視覚化
        self.mirror_horizontal = False  # 左右反転モード：水平方向の反転
        self.merge_mode = "improved"

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
            page_orientation=self.page_orientation,
            mirror_horizontal=self.mirror_horizontal,
        )

        # ═══ 処理統計情報：品質管理と性能監視のためのメトリクス ═══
        self.stats = {
            "total_faces": 0,  # 総面数：入力モデルの複雑さ指標
            "planar_faces": 0,  # 平面数：直接展開可能な面の数
            "cylindrical_faces": 0,  # 円筒面数：円筒展開対象面の数
            "conical_faces": 0,  # 円錐面数：円錐展開対象面の数
            "other_faces": 0,  # その他面数：特殊処理が必要な面の数
            "unfoldable_faces": 0,  # 展開可能面数：最終的に展開された面の数
            "processing_time": 0.0,  # 処理時間：性能評価指標（秒単位）
        }
        self.texture_mappings: List[Dict[str, Any]] = []
        self.generate_unfolding_net = False

    def apply_source_face_descriptors(self, source_descriptors: List[Dict[str, Any]]) -> None:
        """Apply stable source face numbers to the imported STEP topology."""
        self._source_face_descriptors = copy.deepcopy(source_descriptors)
        if not self._analysis_ready:
            return
        self._match_source_face_descriptors()
        self.unfold_engine.set_geometry_data(
            self.faces_data,
            self.edges_data,
            self.geometry_analyzer.adjacency_map,
        )

    def _match_source_face_descriptors(self) -> None:
        source_descriptors = self._source_face_descriptors
        if not source_descriptors:
            return
        self._face_match_warnings.clear()
        for face in self.faces_data:
            face.pop("source_node_index", None)
            face.pop("source_face_index", None)
        matches, unmatched_faces = match_source_face_descriptors(
            self.faces_data, source_descriptors
        )
        matched_faces = set()
        for face_index, source_index in matches:
            source = source_descriptors[source_index]
            face = self.faces_data[face_index]
            face["face_number"] = int(source["faceNumber"])
            face["source_node_index"] = int(source["nodeIndex"])
            face["source_face_index"] = int(source["faceIndex"])
            matched_faces.add(face_index)

        for face_index, face in enumerate(self.faces_data):
            if face_index not in matched_faces:
                face["face_number"] = None

        if unmatched_faces:
            self._face_match_warnings.append(
                {
                    "type": "face_correspondence_incomplete",
                    "message": "一部のSTEP面を元の3D面へ安全に対応付けできなかったため、該当する展開面の番号を省略しました。",
                    "details": {
                        "matched_faces": len(matches),
                        "source_faces": len(source_descriptors),
                        "step_faces": len(self.faces_data),
                        "unmatched_step_faces": unmatched_faces,
                    },
                }
            )

    def set_texture_mappings(self, texture_mappings: List[Dict[str, Any]]):
        """
        テクスチャマッピング情報を設定する。

        Args:
            texture_mappings: [{faceNumber: int, patternId: str, tileCount: int}, ...]
        """
        self.texture_mappings = texture_mappings
        logger.info(f"[StepUnfoldGenerator] Set {len(texture_mappings)} texture mappings")

    def load_from_file(self, file_path: str) -> bool:
        """
        ファイル拡張子に応じて適切な読み込み関数を呼び出す。
        """
        # ファイルハッシュを計算（キャッシュキー用）
        try:
            with open(file_path, "rb") as f:
                self._file_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            self._file_hash = None

        self._analysis_ready = False

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
        # ファイルハッシュを計算（キャッシュキー用）
        self._file_hash = hashlib.sha256(file_content).hexdigest()

        self._analysis_ready = False
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
        # ファイルハッシュを計算（キャッシュキー用）
        self._file_hash = hashlib.sha256(file_content).hexdigest()

        self._analysis_ready = False
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
        SHA256ハッシュによるキャッシュで同一ファイルの再解析を回避。
        """
        if self.solid_shape is None:
            raise ValueError("BREPデータが読み込まれていません")
        if self._analysis_ready:
            return

        # キャッシュヒットチェック
        if self._file_hash and self._file_hash in self._analysis_cache:
            cached = self._analysis_cache[self._file_hash]
            logger.info(f"[Cache HIT] 解析キャッシュを使用: {self._file_hash[:12]}...")

            # LRU: アクセスしたエントリを末尾に移動
            self._analysis_cache.move_to_end(self._file_hash)

            # ディープコピーしてリクエスト間のデータ汚染を防止
            self.geometry_analyzer.faces_data = copy.deepcopy(cached["faces_data"])
            self.geometry_analyzer.edges_data = copy.deepcopy(cached["edges_data"])
            self.geometry_analyzer.adjacency_map = copy.deepcopy(
                cached["adjacency_map"]
            )

            # 共有参照を再設定
            self.faces_data = self.geometry_analyzer.faces_data
            self.edges_data = self.geometry_analyzer.edges_data

            # 統計情報復元
            for key in cached["stats"]:
                self.geometry_analyzer.stats[key] = cached["stats"][key]
                if key in self.stats:
                    self.stats[key] = cached["stats"][key]

            # 展開エンジンに幾何学データを設定
            self.unfold_engine.set_geometry_data(
                self.faces_data,
                self.edges_data,
                self.geometry_analyzer.adjacency_map,
            )
            self._analysis_ready = True
            self._match_source_face_descriptors()
            self.unfold_engine.set_geometry_data(
                self.faces_data,
                self.edges_data,
                self.geometry_analyzer.adjacency_map,
            )
            return

        # キャッシュミス: 通常の解析を実行
        logger.info(
            f"[Cache MISS] OCCT解析を実行"
            + (f": {self._file_hash[:12]}..." if self._file_hash else "")
        )
        self.geometry_analyzer.analyze_brep_topology(self.solid_shape)

        # 統計情報更新
        self.stats["total_faces"] = self.geometry_analyzer.stats["total_faces"]
        self.stats["planar_faces"] = self.geometry_analyzer.stats["planar_faces"]
        self.stats["cylindrical_faces"] = self.geometry_analyzer.stats[
            "cylindrical_faces"
        ]
        self.stats["conical_faces"] = self.geometry_analyzer.stats["conical_faces"]
        self.stats["other_faces"] = self.geometry_analyzer.stats["other_faces"]

        # 展開エンジンに幾何学データを設定
        self.unfold_engine.set_geometry_data(
            self.faces_data,
            self.edges_data,
            self.geometry_analyzer.adjacency_map,
        )

        # キャッシュに保存（ディープコピー）
        if self._file_hash:
            cache_entry = {
                "faces_data": copy.deepcopy(self.geometry_analyzer.faces_data),
                "edges_data": copy.deepcopy(self.geometry_analyzer.edges_data),
                "adjacency_map": copy.deepcopy(self.geometry_analyzer.adjacency_map),
                "stats": {
                    "total_faces": self.geometry_analyzer.stats["total_faces"],
                    "planar_faces": self.geometry_analyzer.stats["planar_faces"],
                    "cylindrical_faces": self.geometry_analyzer.stats[
                        "cylindrical_faces"
                    ],
                    "conical_faces": self.geometry_analyzer.stats["conical_faces"],
                    "other_faces": self.geometry_analyzer.stats["other_faces"],
                },
            }
            self._analysis_cache[self._file_hash] = cache_entry

            # LRUエビクション: 最大サイズを超えた場合、最も古いエントリを削除
            while len(self._analysis_cache) > self._CACHE_MAX_SIZE:
                evicted_key, _ = self._analysis_cache.popitem(last=False)
                logger.info(f"[Cache EVICT] キャッシュエビクション: {evicted_key[:12]}...")

            logger.info(
                f"[Cache STORE] 解析結果をキャッシュ: {self._file_hash[:12]}... "
                f"(キャッシュサイズ: {len(self._analysis_cache)}/{self._CACHE_MAX_SIZE})"
            )

        self._analysis_ready = True
        self._match_source_face_descriptors()
        self.unfold_engine.set_geometry_data(
            self.faces_data,
            self.edges_data,
            self.geometry_analyzer.adjacency_map,
        )

    def group_faces_for_unfolding(self, max_faces: int = 20) -> List[List[int]]:
        """
        展開可能な面をグループ化。
        展開エンジンに処理を委譲。
        """
        # 展開エンジンの設定を更新
        self.unfold_engine.scale_factor = self.scale_factor
        self.unfold_engine.tab_width = self.tab_width
        self.unfold_engine.merge_mode = self.merge_mode
        self.unfold_engine.merge_mode = self.merge_mode

        # 展開エンジンに処理を委譲
        self.unfold_groups = self.unfold_engine.group_faces_for_unfolding(
            max_faces=max_faces,
            generate_unfolding_net=self.generate_unfolding_net,
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

    def apply_request_settings(self, request: BrepPapercraftRequest) -> None:
        """
        リクエストパラメータを内部設定へ反映する。
        """
        self.scale_factor = request.scale_factor
        self.scale_mode = request.scale_mode
        self.applied_scale_factor = request.scale_factor
        self.units = request.units
        self.tab_width = request.tab_width
        self.show_scale = request.show_scale
        self.show_fold_lines = request.show_fold_lines
        self.show_cut_lines = request.show_cut_lines
        self.layout_mode = request.layout_mode
        self.page_format = request.page_format
        self.page_orientation = request.page_orientation
        self.mirror_horizontal = request.mirror_horizontal
        self.merge_mode = request.merge_mode
        self.curve_mode = request.curve_mode

        self.unfold_engine.scale_factor = self.scale_factor
        self.unfold_engine.tab_width = self.tab_width
        self.unfold_engine.merge_mode = self.merge_mode
        self.unfold_engine.curve_mode = self.curve_mode
        self.unfold_engine.curve_tolerance = (
            0.5 * self.scale_factor / self._source_unit_to_mm_factor()
        )
        self.unfold_engine.curve_stats = {
            "reconstructed_cylinders": 0,
            "reconstructed_cones": 0,
            "rejected": 0,
        }
        self.layout_manager.update_scale_factor(self.scale_factor)
        self.layout_manager.update_page_settings(
            page_format=self.page_format, page_orientation=self.page_orientation
        )
        self.svg_exporter.update_settings(
            scale_factor=self.scale_factor,
            units=self.units,
            tab_width=self.tab_width,
            show_scale=self.show_scale,
            show_fold_lines=self.show_fold_lines,
            show_cut_lines=self.show_cut_lines,
            layout_mode=self.layout_mode,
            page_format=self.page_format,
            page_orientation=self.page_orientation,
            mirror_horizontal=self.mirror_horizontal,
        )

    def _source_unit_to_mm_factor(self) -> float:
        """
        入力座標の単位を実寸mmへ変換する係数を返す。
        """
        factors = {
            "mm": 1.0,
            "cm": 10.0,
            "m": 1000.0,
        }
        try:
            return factors[self.units]
        except KeyError as exc:
            raise ValueError("unitsはmm/cm/mのいずれかを指定してください") from exc

    def _calculate_fit_page_scale_factor(self, unfolded_groups: List[Dict]) -> float:
        """
        一番大きい展開グループが選択用紙1枚に収まる最大縮尺を計算する。
        複数グループのページ分割は後段のlayout_for_pagesに委譲する。
        戻り値は縮尺分母（例: 150 = 1:150）。
        """
        required_scale = None
        printable_width = self.layout_manager.printable_width_mm
        printable_height = self.layout_manager.printable_height_mm
        for group in unfolded_groups:
            paper_unit_group = self._scale_unfolded_groups_to_paper([group], 1.0)[0]
            group_required_scale = self.layout_manager.required_scale_to_fit_group(
                paper_unit_group, printable_width, printable_height
            )
            required_scale = (
                group_required_scale
                if required_scale is None
                else max(required_scale, group_required_scale)
            )

        return required_scale or 1.0

    def _scale_unfolded_groups_to_paper(
        self, unfolded_groups: List[Dict], scale_factor: float
    ) -> List[Dict]:
        """
        展開済みグループを実物寸法(mm)から紙上寸法(mm)へ変換する。
        """
        if scale_factor <= 0:
            raise ValueError("scale_factorは0より大きい必要があります")

        scale = self._source_unit_to_mm_factor() / scale_factor
        scaled_groups = []

        for group in unfolded_groups:
            scaled_group = copy.deepcopy(group)
            scaled_group["polygons"] = [
                [(x * scale, y * scale) for x, y in polygon]
                for polygon in group.get("polygons", [])
            ]
            scaled_group["tabs"] = [
                [(x * scale, y * scale) for x, y in tab]
                for tab in group.get("tabs", [])
            ]
            scaled_group["fold_lines"] = [
                [(x * scale, y * scale) for x, y in line]
                for line in group.get("fold_lines", [])
            ]
            scaled_group["cut_lines"] = [
                [(x * scale, y * scale) for x, y in line]
                for line in group.get("cut_lines", [])
            ]
            scaled_group["bbox"] = self.layout_manager.calculate_group_bbox(
                scaled_group
            )
            scaled_groups.append(scaled_group)

        return scaled_groups

    def _split_extreme_multi_ring_groups(self, unfolded_groups: List[Dict]) -> List[Dict]:
        """
        同方向結合で発生する極端に細長い複数リンググループを分割する。
        PLATEAUでは同じ向きの小面が長い列として結合されることがあり、
        その全体bboxを1パーツ扱いすると用紙最大縮尺が過剰に小さくなる。
        """
        split_groups = []

        for group in unfolded_groups:
            polygons = group.get("polygons", [])
            face_indices = group.get("face_indices", [])
            if len(polygons) <= 1 or len(face_indices) <= 1:
                split_groups.append(group)
                continue

            bbox = self.layout_manager.calculate_group_bbox(group)
            shorter = max(min(bbox["width"], bbox["height"]), 1e-9)
            aspect_ratio = max(bbox["width"], bbox["height"]) / shorter
            if aspect_ratio < 20.0:
                split_groups.append(group)
                continue

            face_numbers = group.get("face_numbers", [])
            for polygon_index, polygon in enumerate(polygons):
                split_group = copy.deepcopy(group)
                split_group["polygons"] = [polygon]
                split_group["tabs"] = []
                split_group["fold_lines"] = []
                split_group["cut_lines"] = []
                if polygon_index < len(face_indices):
                    split_group["face_indices"] = [face_indices[polygon_index]]
                if polygon_index < len(face_numbers):
                    split_group["face_numbers"] = [face_numbers[polygon_index]]
                split_group["component_index"] = polygon_index
                split_groups.append(split_group)

        return split_groups

    def _prepare_groups_for_layout(
        self, unfolded_groups: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        縮尺モードに応じて、展開グループを紙上寸法に変換する。
        """
        warnings = []
        requested_scale_factor = self.scale_factor
        if self.merge_mode == "improved":
            unfolded_groups = self._split_extreme_multi_ring_groups(unfolded_groups)

        if self.scale_mode == "fit_page":
            self.applied_scale_factor = self._calculate_fit_page_scale_factor(
                unfolded_groups
            )
        else:
            self.applied_scale_factor = requested_scale_factor

        paper_groups = self._scale_unfolded_groups_to_paper(
            unfolded_groups, self.applied_scale_factor
        )

        self.stats["scale_mode"] = self.scale_mode
        self.stats["requested_scale_factor"] = requested_scale_factor
        self.stats["applied_scale_factor"] = round(self.applied_scale_factor, 6)
        self.stats["source_units"] = self.units
        self.stats["unit_to_mm_factor"] = self._source_unit_to_mm_factor()
        self.stats["page_format"] = self.page_format
        self.stats["page_orientation"] = self.page_orientation
        self.stats["merge_mode"] = self.merge_mode
        self.stats["curve_mode"] = self.curve_mode
        self.stats["curve_reconstruction"] = copy.deepcopy(
            self.unfold_engine.curve_stats
        )

        if self.scale_mode == "fit_page":
            warnings.append(
                {
                    "type": "fit_page_scale_applied",
                    "message": (
                        f"用紙最大モードにより 1:{self.applied_scale_factor:.1f} "
                        "で展開図を生成しました。"
                    ),
                    "details": {
                        "applied_scale_factor": round(self.applied_scale_factor, 6),
                        "page_format": self.page_format,
                        "page_orientation": self.page_orientation,
                        "printable_area_mm": {
                            "width": self.layout_manager.printable_width_mm,
                            "height": self.layout_manager.printable_height_mm,
                        },
                    },
                }
            )

        return paper_groups, warnings

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
            page_orientation=self.page_orientation,
            mirror_horizontal=self.mirror_horizontal,
        )

        # テクスチャマッピングを設定
        if self.texture_mappings:
            self.svg_exporter.set_texture_mappings(self.texture_mappings)

        # SVGエクスポーターに処理を委譲
        return self.svg_exporter.export_to_svg(
            placed_groups, output_path, self.layout_manager
        )

    def export_to_svg_paged_single_file(
        self, paged_groups: List[List[Dict]], output_path: str
    ) -> str:
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
            page_orientation=self.page_orientation,
            mirror_horizontal=self.mirror_horizontal,
        )

        # テクスチャマッピングを設定
        if self.texture_mappings:
            self.svg_exporter.set_texture_mappings(self.texture_mappings)

        # SVGエクスポーターに処理を委譲
        return self.svg_exporter.export_to_svg_paged_single_file(
            paged_groups, output_path
        )

    def export_to_svg_paged_files(
        self, paged_groups: List[List[Dict]], output_dir: str
    ) -> List[str]:
        """
        ページ分割された展開図を複数SVGファイルとして出力。
        """
        self.svg_exporter.update_settings(
            scale_factor=self.scale_factor,
            units=self.units,
            tab_width=self.tab_width,
            show_scale=self.show_scale,
            show_fold_lines=self.show_fold_lines,
            show_cut_lines=self.show_cut_lines,
            layout_mode=self.layout_mode,
            page_format=self.page_format,
            page_orientation=self.page_orientation,
            mirror_horizontal=self.mirror_horizontal,
        )

        if self.texture_mappings:
            self.svg_exporter.set_texture_mappings(self.texture_mappings)

        return self.svg_exporter.export_to_svg_paged(paged_groups, output_dir)

    def export_to_pdf_paged(
        self, paged_groups: List[List[Dict]], output_path: str
    ) -> str:
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
        logger.info(f"PDFエクスポート開始: {len(paged_groups)}ページ")

        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp()
        svg_paths = []

        try:
            # 各ページを個別のSVGファイルとして保存
            svg_paths = self.export_to_svg_paged_files(paged_groups, temp_dir)

            logger.info(f"SVG生成完了: {len(svg_paths)}ファイル")

            # PDFExporterを初期化
            pdf_exporter = PDFExporter(
                page_format=self.page_format, page_orientation=self.page_orientation
            )

            # SVGファイルリストからPDFを生成
            result_path = pdf_exporter.export_svg_list_to_pdf(svg_paths, output_path)

            logger.info(f"PDFエクスポート完了: {result_path}")

            return result_path

        finally:
            # 一時ファイルをクリーンアップ
            import shutil

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"一時ディレクトリを削除: {temp_dir}")

    def generate_brep_papercraft_pages(
        self, request: BrepPapercraftRequest
    ) -> Tuple[List[List[Dict]], Dict]:
        """
        BREPソリッドからページ単位の展開図データを生成する。
        """
        if self.solid_shape is None:
            raise ValueError("BREPソリッドが読み込まれていません")
        if request.layout_mode != "paged":
            raise ValueError("paged出力は layout_mode='paged' のみ対応しています")

        try:
            start_time = time.time()

            self.apply_request_settings(request)

            self.analyze_brep_topology()
            self.group_faces_for_unfolding(request.max_faces)
            unfolded_groups = self.unfold_face_groups()
            paper_groups, scale_warnings = self._prepare_groups_for_layout(
                unfolded_groups
            )
            warnings = self._face_match_warnings + scale_warnings

            paged_groups, layout_warnings = self.layout_manager.layout_for_pages(
                paper_groups
            )
            self._remember_exported_face_numbers(
                group for page in paged_groups for group in page
            )
            warnings += layout_warnings

            end_time = time.time()
            self.stats["processing_time"] = end_time - start_time
            self.stats["unfoldable_faces"] = sum(
                len(group["polygons"]) for page in paged_groups for group in page
            )
            self.stats["layout_mode"] = "paged"
            self.stats["page_count"] = len(paged_groups)
            if warnings:
                self.stats["warnings"] = warnings

            return paged_groups, self.stats

        except Exception as e:
            import traceback

            traceback.print_exc()
            raise ValueError(f"BREP展開図生成エラー: {str(e)}")

    def generate_brep_papercraft(
        self, request: BrepPapercraftRequest, output_path: Optional[str] = None
    ) -> Tuple[str, Dict]:
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

            self.apply_request_settings(request)

            # 1. BREPトポロジ解析
            self.analyze_brep_topology()

            # 2. 展開可能面のグルーピング
            self.group_faces_for_unfolding(request.max_faces)

            # 3. 各グループの2D展開
            unfolded_groups = self.unfold_face_groups()
            paper_groups, scale_warnings = self._prepare_groups_for_layout(
                unfolded_groups
            )
            warnings = self._face_match_warnings + scale_warnings

            # 4. レイアウトモードに応じた配置
            if self.layout_mode == "paged":
                # ページモード: ページ単位でレイアウト
                self.layout_manager.update_page_settings(
                    page_format=self.page_format, page_orientation=self.page_orientation
                )
                paged_groups, layout_warnings = self.layout_manager.layout_for_pages(
                    paper_groups
                )
                self._remember_exported_face_numbers(
                    group for page in paged_groups for group in page
                )
                warnings += layout_warnings

                # 5. 単一SVGファイルに全ページを出力
                svg_path = self.export_to_svg_paged_single_file(
                    paged_groups, output_path
                )

                # 統計情報にページ数を追加
                self.stats["page_count"] = len(paged_groups)
                self.stats["svg_files"] = [svg_path]  # 単一ファイル
                # 警告情報を追加
                if warnings:
                    self.stats["warnings"] = warnings
            else:
                # キャンバスモード: 従来の単一SVG
                placed_groups = self.layout_unfolded_groups(paper_groups)
                self._remember_exported_face_numbers(placed_groups)

                # 5. SVG出力
                svg_path = self.export_to_svg(placed_groups, output_path)

            # 処理統計更新
            end_time = time.time()
            self.stats["processing_time"] = end_time - start_time
            self.stats["unfoldable_faces"] = sum(
                len(group["polygons"])
                for page in (
                    paged_groups if self.layout_mode == "paged" else [placed_groups]
                )
                for group in (page if self.layout_mode == "paged" else placed_groups)
            )
            self.stats["layout_mode"] = self.layout_mode
            if warnings:
                self.stats["warnings"] = warnings

            return svg_path, self.stats

        except Exception as e:
            import traceback

            traceback.print_exc()
            raise ValueError(f"BREP展開図生成エラー: {str(e)}")

    def _remember_exported_face_numbers(self, groups) -> None:
        """Map every exported source face number to its SVG group label."""
        exported: Dict[int, int] = {}
        for group in groups:
            if not group.get("polygons"):
                continue
            face_numbers = group.get("face_numbers") or []
            # SVGExporter emits one label per placed group using its first number.
            representative = face_numbers[0] if face_numbers else None
            if representative is None:
                continue
            representative = int(representative)
            for face_number in face_numbers:
                if face_number is not None:
                    exported.setdefault(int(face_number), representative)
        self._exported_face_number_map = exported

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
                if face_number is None:
                    continue
                displayed_face_number = face_number
                if self._exported_face_number_map is not None:
                    displayed_face_number = self._exported_face_number_map.get(int(face_number))
                    if displayed_face_number is None:
                        continue
                item = {
                    "faceIndex": face_data.get("source_face_index", face_data.get("index", face_index)),
                    "faceNumber": displayed_face_number,
                }
                if "source_node_index" in face_data:
                    item["nodeIndex"] = face_data["source_node_index"]
                face_numbers.append(item)

        logger.info(
            f"StepUnfoldGenerator.get_face_numbers(): {len(face_numbers)}個の面番号データを返します"
        )
        return face_numbers
