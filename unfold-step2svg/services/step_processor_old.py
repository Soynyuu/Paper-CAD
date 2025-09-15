import os
import tempfile
import uuid
import base64
import json
import math
import time
from typing import List, Optional, Dict, Any, Union, Tuple
import numpy as np
import svgwrite
from scipy.spatial import ConvexHull
from scipy.spatial.distance import cdist
import networkx as nx
import io

from config import OCCT_AVAILABLE
from core.file_loaders import FileLoader
from core.geometry_analyzer import GeometryAnalyzer
from core.unfold_engine import UnfoldEngine

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
        self.units = "mm"           # 単位系：寸法の解釈基準
        self.tab_width = 5.0        # タブ幅：接着部の物理的寸法
        self.show_scale = True      # スケールバー：図面標準への準拠
        self.show_fold_lines = True # 折り線：組み立て指示の視覚化
        self.show_cut_lines = True  # 切断線：加工指示の視覚化
        
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
        self.unfold_groups = self.unfold_engine.group_faces_for_unfolding(max_faces)
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



    def _extract_face_2d_shape(self, face_idx: int, normal: np.ndarray, origin: np.ndarray) -> List[List[Tuple[float, float]]]:
        """
        面の正確な2D形状を抽出（外形線・内形線を考慮）。
        """
        face_data = self.faces_data[face_idx]
        polygons_2d = []
        
        print(f"面{face_idx}の2D形状を抽出中...")
        print(f"  境界線数: {len(face_data['boundary_curves'])}")
        
        # 各境界線を2Dに投影
        for boundary_idx, boundary in enumerate(face_data["boundary_curves"]):
            print(f"  境界線{boundary_idx}: {len(boundary)}点")
            
            if len(boundary) >= 3:
                # 3D境界点を2D平面に正確に投影
                projected_boundary = self._project_points_to_plane_accurate(boundary, normal, origin)
                
                # 境界線を単純化（正方形/長方形の場合は4点に削減）
                simplified_boundary = self._simplify_boundary_polygon(projected_boundary)
                
                # 有効な2D形状の場合のみ追加
                if len(simplified_boundary) >= 3:
                    polygons_2d.append(simplified_boundary)
                    print(f"  境界線{boundary_idx}を2D投影: {len(simplified_boundary)}点（簡略化済み）")
                else:
                    print(f"  境界線{boundary_idx}の投影に失敗")
            else:
                print(f"  境界線{boundary_idx}の点数が不足: {len(boundary)}点")
        
        print(f"面{face_idx}の2D形状: {len(polygons_2d)}個のポリゴン")
        return polygons_2d

    def _remove_duplicate_points_2d(self, points_2d: List[Tuple[float, float]], tolerance: float = 1e-6) -> List[Tuple[float, float]]:
        """
        重複点を除去（2D点用）。
        """
        if len(points_2d) < 2:
            return points_2d
        
        cleaned_points = [points_2d[0]]
        
        for i in range(1, len(points_2d)):
            current = points_2d[i]
            last = cleaned_points[-1]
            
            # 距離チェック
            distance = math.sqrt((current[0] - last[0])**2 + (current[1] - last[1])**2)
            if distance > tolerance:
                cleaned_points.append(current)
        
        # 最初と最後の点が重複している場合は除去
        if len(cleaned_points) > 2:
            first = cleaned_points[0]
            last = cleaned_points[-1]
            distance = math.sqrt((first[0] - last[0])**2 + (first[1] - last[1])**2)
            if distance <= tolerance:
                cleaned_points = cleaned_points[:-1]
        
        return cleaned_points

    def _ensure_counterclockwise_order(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        境界線の点を反時計回りに並び替え（SVG描画に適した順序）。
        """
        if len(points_2d) < 3:
            return points_2d
        
        # 符号付き面積を計算（反時計回りなら正）
        signed_area = 0.0
        n = len(points_2d)
        
        for i in range(n):
            j = (i + 1) % n
            signed_area += (points_2d[j][0] - points_2d[i][0]) * (points_2d[j][1] + points_2d[i][1])
        
        # 時計回りの場合は順序を反転
        if signed_area > 0:
            return list(reversed(points_2d))
        else:
            return points_2d

    def _simplify_boundary_polygon(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        境界線ポリゴンを簡略化（形状に応じて適切な点数に削減）。
        """
        if len(points_2d) < 3:
            return points_2d
        
        # 重複点を除去
        cleaned_points = self._remove_duplicate_points_2d(points_2d)
        
        if len(cleaned_points) < 3:
            return cleaned_points
        
        print(f"        境界線簡略化: {len(points_2d)}点 → ", end="")
        
        # 三角形の場合
        if self._is_triangular_boundary(cleaned_points):
            result = self._extract_triangle_corners(cleaned_points)
            print(f"{len(result)}点（三角形）")
            return result
            
        # 四角形の場合
        if self._is_rectangular_boundary(cleaned_points):
            result = self._extract_rectangle_corners(cleaned_points)
            print(f"{len(result)}点（四角形）")
            return result
        
        # 五角形の場合（家の形状）
        if self._is_pentagonal_boundary(cleaned_points):
            result = self._extract_pentagon_corners(cleaned_points)
            print(f"{len(result)}点（五角形）")
            return result
        
        # その他の多角形は適度に間引く
        result = self._thin_out_points(cleaned_points, max_points=12)
        print(f"{len(result)}点（一般多角形）")
        return result
    
    def _is_triangular_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が三角形かどうかを判定。
        """
        if len(points_2d) < 6:  # 最低でも6点は必要
            return False
        
        # 凸包を計算して3点になるかチェック
        try:
            import numpy as np
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点が3個なら三角形
            return len(hull.vertices) == 3
        except:
            return False
    
    def _extract_triangle_corners(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点群から三角形の3つの角を抽出。
        """
        try:
            import numpy as np
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点を取得
            triangle_corners = [tuple(points_array[i]) for i in hull.vertices]
            
            # 3点になるように調整
            if len(triangle_corners) == 3:
                # 時計回りに並び替え
                triangle_corners = self._sort_points_clockwise(triangle_corners)
                # 閉じた三角形にする
                triangle_corners.append(triangle_corners[0])
                return triangle_corners
            else:
                # フォールバック：最初の3点を使用
                return points_2d[:4]  # 最初の3点+閉じる点
        except:
            return points_2d[:4]  # フォールバック
    
    def _sort_points_clockwise(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点を時計回りに並び替え。
        """
        # 重心を計算
        center_x = sum(p[0] for p in points) / len(points)
        center_y = sum(p[1] for p in points) / len(points)
        
        # 角度でソート
        import math
        def angle_from_center(point):
            return math.atan2(point[1] - center_y, point[0] - center_x)
        
        sorted_points = sorted(points, key=angle_from_center)
        return sorted_points
    
    def _is_rectangular_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が四角形（正方形・長方形）かどうかを判定。
        """
        if len(points_2d) < 8:  # 最低でも8点は必要
            return False
        
        # 凸包を計算して4点になるかチェック
        try:
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点が4個なら四角形の可能性
            if len(hull.vertices) == 4:
                return True
        except:
            pass
        
        # フォールバック：境界ボックスベースの判定
        xs = [p[0] for p in points_2d]
        ys = [p[1] for p in points_2d]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # 境界ボックスの角に近い点の数を確認
        tolerance = 0.1
        corner_count = 0
        corners = [
            (min_x, min_y), (max_x, min_y), 
            (max_x, max_y), (min_x, max_y)
        ]
        
        for corner in corners:
            for point in points_2d:
                distance = math.sqrt((point[0] - corner[0])**2 + (point[1] - corner[1])**2)
                if distance < tolerance:
                    corner_count += 1
                    break
        
        return corner_count >= 4
    
    def _extract_rectangle_corners(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点群から四角形の4つの角を抽出。
        """
        try:
            # 凸包を使用して角を抽出
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            if len(hull.vertices) == 4:
                # 凸包の頂点を時計回りに並び替え
                rectangle_corners = [tuple(points_array[i]) for i in hull.vertices]
                rectangle_corners = self._sort_points_clockwise(rectangle_corners)
                # 閉じた四角形にする
                rectangle_corners.append(rectangle_corners[0])
                return rectangle_corners
        except:
            pass
        
        # フォールバック：境界ボックスベースの抽出
        xs = [p[0] for p in points_2d]
        ys = [p[1] for p in points_2d]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # 4つの角を時計回りに並べる
        corners = [
            (min_x, min_y),  # 左下
            (max_x, min_y),  # 右下
            (max_x, max_y),  # 右上
            (min_x, max_y),  # 左上
            (min_x, min_y)   # 閉じる
        ]
        
        return corners
    
    def _is_pentagonal_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が五角形かどうかを判定。
        """
        # 仮実装：常にFalseを返す
        return False
    
    def _extract_pentagon_corners(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点群から五角形の5つの角を抽出。
        """
        # 仮実装：元の点をそのまま返す
        return points_2d
    
    def _thin_out_points(self, points_2d: List[Tuple[float, float]], max_points: int = 12) -> List[Tuple[float, float]]:
        """
        点群を適度に間引く。
        """
        if len(points_2d) <= max_points:
            return points_2d
            
        # 等間隔で点を選択
        step = len(points_2d) // max_points
        return [points_2d[i] for i in range(0, len(points_2d), step)]

    def _project_points_to_plane_accurate(self, points_3d: List[Tuple[float, float, float]], 
                                         normal: np.ndarray, origin: np.ndarray) -> List[Tuple[float, float]]:
        """
        3D点群を平面に正確に投影（直交座標系を構築）。
        """
        if len(points_3d) < 3:
            return []
        
        # 平面の直交座標系を構築
        normal = normal / np.linalg.norm(normal)
        
        # 第1軸：より安定した方向ベクトル選択
        if abs(normal[0]) < 0.9:
            u_axis = np.cross(normal, [1, 0, 0])
        elif abs(normal[1]) < 0.9:
            u_axis = np.cross(normal, [0, 1, 0])
        else:
            u_axis = np.cross(normal, [0, 0, 1])
        
        # ゼロベクトルチェック
        if np.linalg.norm(u_axis) < 1e-8:
            u_axis = np.array([1, 0, 0])
        else:
            u_axis = u_axis / np.linalg.norm(u_axis)
        
        # 第2軸：法線と第1軸の外積
        v_axis = np.cross(normal, u_axis)
        v_axis = v_axis / np.linalg.norm(v_axis)
        
        points_2d = []
        
        for point in points_3d:
            # 原点からの相対位置
            relative_pos = np.array(point) - origin
            
            # 平面座標系での座標計算
            u = np.dot(relative_pos, u_axis)
            v = np.dot(relative_pos, v_axis)
            
            points_2d.append((u, v))
        
        # 境界線の順序を確認・修正
        if len(points_2d) >= 3:
            points_2d = self._ensure_counterclockwise_order(points_2d)
        
        return points_2d

    def _unfold_cylindrical_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        円筒面グループの展開（正確な円筒座標→直交座標変換）。
        円筒面と円形の蓋を組み合わせて、実際に組み立て可能な展開図を生成。
        """
        polygons = []
        
        # 円筒面と平面（蓋）を分離
        cylindrical_faces = []
        planar_faces = []
        
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            if face_data["surface_type"] == "cylinder":
                cylindrical_faces.append(face_idx)
            elif face_data["surface_type"] == "plane":
                planar_faces.append(face_idx)
        
        # 円筒面の展開
        for face_idx in cylindrical_faces:
            face_data = self.faces_data[face_idx]
            
            # 円筒パラメータ
            axis = np.array(face_data["cylinder_axis"])
            center = np.array(face_data["cylinder_center"])
            radius = face_data["cylinder_radius"]
            
            # 円筒面の正確な2D形状を取得
            cylinder_polygons = self._extract_cylindrical_face_2d(face_idx, axis, center, radius)
            if cylinder_polygons:
                polygons.extend(cylinder_polygons)
        
        # 円形の蓋を追加（平面の場合）
        for face_idx in planar_faces:
            face_data = self.faces_data[face_idx]
            
            # 平面が円形かどうか確認
            if self._is_circular_face(face_data):
                # 円形の蓋を展開図に追加
                circle_polygon = self._extract_circular_face_2d(face_data)
                if circle_polygon:
                    polygons.append(circle_polygon)
        
        return {
            "group_index": group_idx,
            "surface_type": "cylinder",
            "polygons": polygons,
            "tabs": self._generate_cylindrical_tabs(cylindrical_faces, planar_faces),
            "unfold_method": "cylindrical_unwrap_with_caps"
        }

    def _extract_cylindrical_face_2d(self, face_idx: int, axis: np.ndarray, center: np.ndarray, 
                                    radius: float) -> List[List[Tuple[float, float]]]:
        """
        円筒面の正確な2D形状を抽出。
        """
        face_data = self.faces_data[face_idx]
        polygons_2d = []
        
        # 各境界線を円筒展開
        for boundary in face_data["boundary_curves"]:
            if len(boundary) >= 3:
                # 3D境界点を円筒展開
                unfolded_boundary = self._unfold_cylindrical_points_accurate(boundary, axis, center, radius)
                
                # 有効な2D形状の場合のみ追加
                if len(unfolded_boundary) >= 3:
                    polygons_2d.append(unfolded_boundary)
        
        return polygons_2d

    def _unfold_cylindrical_points_accurate(self, points_3d: List[Tuple[float, float, float]], 
                                           axis: np.ndarray, center: np.ndarray, 
                                           radius: float) -> List[Tuple[float, float]]:
        """
        3D点群を円筒面から正確に展開（改良版）。
        """
        if len(points_3d) < 3:
            return []
        
        # 軸の単位ベクトル化
        axis = axis / np.linalg.norm(axis)
        points_2d = []
        
        # 基準方向ベクトル設定
        if abs(axis[2]) < 0.9:
            ref_dir = np.cross(axis, [0, 0, 1])
        else:
            ref_dir = np.cross(axis, [1, 0, 0])
        ref_dir = ref_dir / np.linalg.norm(ref_dir)
        
        for point in points_3d:
            point_vec = np.array(point) - center
            
            # 軸方向成分（Y座標）
            y = np.dot(point_vec, axis)
            
            # 軸に垂直な成分
            radial_vec = point_vec - y * axis
            radial_dist = np.linalg.norm(radial_vec)
            
            # 角度計算（X座標）
            if radial_dist > 1e-6:
                # 正確な角度計算
                cos_angle = np.dot(radial_vec, ref_dir) / radial_dist
                cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値エラー対策
                
                # 符号を決定するための外積
                cross_product = np.cross(ref_dir, radial_vec)
                sign = 1 if np.dot(cross_product, axis) >= 0 else -1
                
                angle = sign * math.acos(cos_angle)
                x = angle * radius
            else:
                x = 0.0
            
            points_2d.append((x, y))
        
        return points_2d

    def _is_circular_face(self, face_data: Dict) -> bool:
        """
        平面が円形かどうかを判定。
        """
        # 仮実装：常にFalseを返す
        return False

    def _extract_circular_face_2d(self, face_data: Dict) -> List[Tuple[float, float]]:
        """
        円形の面を2D形状として抽出。
        """
        # 仮実装：空リストを返す
        return []

    def _generate_cylindrical_tabs(self, cylindrical_faces: List[int], planar_faces: List[int]) -> List[List[Tuple[float, float]]]:
        """
        円筒面グループ用のタブを生成。
        """
        # 仮実装：空リストを返す
        return []

    def _unfold_conical_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        円錐面グループの展開（円錐展開図）。
        """
        polygons = []
        
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            
            # 円錐パラメータ
            apex = np.array(face_data["cone_apex"])
            axis = np.array(face_data["cone_axis"])
            radius = face_data["cone_radius"]
            semi_angle = face_data["cone_semi_angle"]
            
            # 円錐面の正確な2D形状を取得
            cone_polygons = self._extract_conical_face_2d(face_idx, apex, axis, radius, semi_angle)
            if cone_polygons:
                polygons.extend(cone_polygons)
        
        return {
            "group_index": group_idx,
            "surface_type": "cone",
            "polygons": polygons,
            "tabs": self._generate_tabs_for_group(face_indices),
            "unfold_method": "conical_unwrap"
        }

    def _extract_conical_face_2d(self, face_idx: int, apex: np.ndarray, axis: np.ndarray, 
                                radius: float, semi_angle: float) -> List[List[Tuple[float, float]]]:
        """
        円錐面の正確な2D形状を抽出。
        """
        face_data = self.faces_data[face_idx]
        polygons_2d = []
        
        # 各境界線を円錐展開
        for boundary in face_data["boundary_curves"]:
            if len(boundary) >= 3:
                # 3D境界点を円錐展開
                unfolded_boundary = self._unfold_conical_points_accurate(boundary, apex, axis, radius, semi_angle)
                
                # 有効な2D形状の場合のみ追加
                if len(unfolded_boundary) >= 3:
                    polygons_2d.append(unfolded_boundary)
        
        return polygons_2d

    def _unfold_conical_points_accurate(self, points_3d: List[Tuple[float, float, float]], 
                                       apex: np.ndarray, axis: np.ndarray, 
                                       radius: float, semi_angle: float) -> List[Tuple[float, float]]:
        """
        3D点群を円錐面から正確に扇形展開。
        """
        if len(points_3d) < 3:
            return []
        
        axis = axis / np.linalg.norm(axis)
        points_2d = []
        
        # 円錐の母線長
        slant_height = radius / math.sin(semi_angle) if semi_angle > 0 else radius
        
        for point in points_3d:
            point_vec = np.array(point) - apex
            
            # 頂点からの距離
            distance = np.linalg.norm(point_vec)
            
            if distance > 1e-6:
                # 軸からの角度
                cos_angle = np.dot(point_vec, axis) / distance
                cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値エラー対策
                angle_from_axis = math.acos(cos_angle)
                
                # 展開図での半径（円錐の母線に沿った距離）
                r = distance * math.cos(angle_from_axis)
                
                # 展開図での角度（円錐の開きを考慮）
                if abs(semi_angle) > 1e-6:
                    # 基準方向ベクトル
                    if abs(axis[2]) < 0.9:
                        ref_dir = np.cross(axis, [0, 0, 1])
                    else:
                        ref_dir = np.cross(axis, [1, 0, 0])
                    ref_dir = ref_dir / np.linalg.norm(ref_dir)
                    
                    # 周方向の角度
                    radial_vec = point_vec - np.dot(point_vec, axis) * axis
                    if np.linalg.norm(radial_vec) > 1e-6:
                        radial_vec = radial_vec / np.linalg.norm(radial_vec)
                        theta = math.atan2(np.dot(radial_vec, np.cross(axis, ref_dir)), 
                                         np.dot(radial_vec, ref_dir))
                        # 円錐展開における角度スケール
                        theta = theta * math.sin(semi_angle)
                    else:
                        theta = 0.0
                else:
                    theta = 0.0
                
                x = r * math.cos(theta)
                y = r * math.sin(theta)
            else:
                x, y = 0.0, 0.0
            
            points_2d.append((x, y))
        
        return points_2d


    def _generate_tabs_for_group(self, face_indices: List[int]) -> List[List[Tuple[float, float]]]:
        """
        面グループ間の接着タブを生成。
        隣接エッジ情報から適切なタブ形状を自動生成。
        """
        tabs = []
        
        # 簡易実装: 各面の境界に矩形タブを配置
        for face_idx in face_indices:
            if face_idx < len(self.faces_data):
                face_data = self.faces_data[face_idx]
                
                for boundary in face_data["boundary_curves"]:
                    if len(boundary) >= 2:
                        # 簡易タブ（矩形）を生成
                        start_point = boundary[0]
                        end_point = boundary[1]
                        
                        # タブの幅
                        tab_width = self.tab_width
                        
                        # 簡易矩形タブ
                        tab = [
                            (start_point[0], start_point[1]),
                            (end_point[0], end_point[1]),
                            (end_point[0], end_point[1] + tab_width),
                            (start_point[0], start_point[1] + tab_width)
                        ]
                        tabs.append(tab)
        
        return tabs

    def layout_unfolded_groups(self, unfolded_groups: List[Dict]) -> List[Dict]:
        """
        展開済みグループを紙面上に効率的に配置。
        重複回避・用紙サイズ最適化を実施。
        """
        if not unfolded_groups:
            return []
        
        # 各グループの境界ボックス計算
        for group in unfolded_groups:
            bbox = self._calculate_group_bbox(group["polygons"])
            group["bbox"] = bbox
        
        # 面積の大きい順にソート
        unfolded_groups.sort(key=lambda g: g["bbox"]["width"] * g["bbox"]["height"], reverse=True)
        
        # 単純な左上から配置アルゴリズム
        placed_groups = []
        next_x = 0
        max_height = 0
        margin = 10 * self.scale_factor
        
        for group in unfolded_groups:
            bbox = group["bbox"]
            
            # グループ全体を移動
            offset_x = next_x - bbox["min_x"]
            offset_y = -bbox["min_y"]
            
            positioned_group = self._translate_group(group, offset_x, offset_y)
            positioned_group["position"] = {"x": next_x, "y": 0}
            
            placed_groups.append(positioned_group)
            
            # 次の配置位置更新
            next_x += bbox["width"] + margin
            max_height = max(max_height, bbox["height"])
        
        return placed_groups

    def _calculate_group_bbox(self, polygons: List[List[Tuple[float, float]]]) -> Dict:
        """グループ全体の境界ボックス計算"""
        if not polygons:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        all_points = []
        for polygon in polygons:
            all_points.extend(polygon)
        
        if not all_points:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        return {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        }

    def _translate_group(self, group: Dict, offset_x: float, offset_y: float) -> Dict:
        """グループ全体を指定オフセットで移動"""
        translated_group = group.copy()
        
        # ポリゴン移動
        translated_polygons = []
        for polygon in group["polygons"]:
            translated_polygon = [(x + offset_x, y + offset_y) for x, y in polygon]
            translated_polygons.append(translated_polygon)
        translated_group["polygons"] = translated_polygons
        
        # タブ移動
        translated_tabs = []
        for tab in group.get("tabs", []):
            translated_tab = [(x + offset_x, y + offset_y) for x, y in tab]
            translated_tabs.append(translated_tab)
        translated_group["tabs"] = translated_tabs
        
        return translated_group

    def export_to_svg(self, placed_groups: List[Dict], output_path: str) -> str:
        """
        配置済み展開図をSVG形式で出力。
        商用品質の印刷対応（スケールバー・図面枠・注記等）。
        """
        if not placed_groups:
            raise ValueError("出力する展開図データがありません")
        
        # 全体境界ボックス計算
        overall_bbox = self._calculate_overall_bbox(placed_groups)
        
        # デバッグ情報
        print(f"全体境界ボックス: {overall_bbox}")
        print(f"現在のscale_factor: {self.scale_factor}")
        
        # SVGキャンバスサイズ決定（最小サイズを保証）
        margin = max(50, 20 * self.scale_factor)  # 最小50px
        min_canvas_size = 800  # 最小キャンバスサイズ
        
        # 適切なスケールファクターを自動計算
        if overall_bbox["width"] > 0 and overall_bbox["height"] > 0:
            # 内容に応じてスケールファクターを調整
            content_scale = min(min_canvas_size / max(overall_bbox["width"], overall_bbox["height"]), 10.0)
            if content_scale > 1.0:
                # 内容が小さすぎる場合はスケールアップ
                self.scale_factor = max(self.scale_factor, content_scale)
                print(f"スケールファクターを自動調整: {self.scale_factor}")
        
        # SVGサイズ計算
        svg_width = max(min_canvas_size, overall_bbox["width"] * self.scale_factor + 2 * margin)
        svg_height = max(min_canvas_size, overall_bbox["height"] * self.scale_factor + 2 * margin + 120)  # タイトル・スケール用
        
        print(f"SVGサイズ: {svg_width} x {svg_height}")
        
        # SVG作成
        dwg = svgwrite.Drawing(output_path, size=(f"{svg_width}px", f"{svg_height}px"), viewBox=f"0 0 {svg_width} {svg_height}")
        
        # 商用グレードスタイル定義
        dwg.defs.add(dwg.style("""
            .face-polygon { fill: none; stroke: #000000; stroke-width: 2; }
            .tab-polygon { fill: none; stroke: #0066cc; stroke-width: 1.5; stroke-dasharray: 4,4; }
            .fold-line { stroke: #ff6600; stroke-width: 1; stroke-dasharray: 6,6; }
            .cut-line { stroke: #ff0000; stroke-width: 0.8; stroke-dasharray: 3,3; }
            .title-text { font-family: Arial, sans-serif; font-size: 24px; font-weight: bold; fill: #000000; }
            .scale-text { font-family: Arial, sans-serif; font-size: 16px; fill: #000000; }
            .note-text { font-family: Arial, sans-serif; font-size: 14px; fill: #666666; }
        """))
        
        # メインコンテンツ描画
        content_offset_x = margin - overall_bbox["min_x"] * self.scale_factor
        content_offset_y = margin - overall_bbox["min_y"] * self.scale_factor + 50  # タイトル分下げる
        
        polygon_count = 0
        
        for group_idx, group in enumerate(placed_groups):
            print(f"グループ{group_idx}をSVGに描画中...")
            print(f"  ポリゴン数: {len(group['polygons'])}")
            
            # 面ポリゴン描画
            for poly_idx, polygon in enumerate(group["polygons"]):
                if len(polygon) >= 3:
                    # スケールファクターを適用
                    points = [(x * self.scale_factor + content_offset_x, y * self.scale_factor + content_offset_y) for x, y in polygon]
                    dwg.add(dwg.polygon(points=points, class_="face-polygon"))
                    polygon_count += 1
                    print(f"  ポリゴン{poly_idx}: {len(polygon)}点を描画")
                else:
                    print(f"  ポリゴン{poly_idx}: 点数不足({len(polygon)}点)")
            
            # タブ描画
            for tab_idx, tab in enumerate(group.get("tabs", [])):
                if len(tab) >= 3:
                    # スケールファクターを適用
                    points = [(x * self.scale_factor + content_offset_x, y * self.scale_factor + content_offset_y) for x, y in tab]
                    dwg.add(dwg.polygon(points=points, class_="tab-polygon"))
                    print(f"  タブ{tab_idx}: {len(tab)}点を描画")
        
        print(f"SVG描画完了: {polygon_count}個のポリゴンを描画")
        
        # タイトル描画
        title = f"BREP Papercraft Unfolding - {len(placed_groups)} Groups"
        dwg.add(dwg.text(title, insert=(margin, 40), class_="title-text"))
        
        # スケールバー描画
        if self.show_scale:
            self._add_scale_bar(dwg, svg_width, svg_height, margin)
        
        # 注記追加
        self._add_technical_notes(dwg, svg_width, svg_height, margin)
        
        # SVG保存
        dwg.save()
        return output_path

    def _calculate_overall_bbox(self, placed_groups: List[Dict]) -> Dict:
        """配置済み全グループの境界ボックス計算"""
        if not placed_groups:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        all_points = []
        for group in placed_groups:
            for polygon in group["polygons"]:
                all_points.extend(polygon)
            for tab in group.get("tabs", []):
                all_points.extend(tab)
        
        if not all_points:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        return {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        }

    def _add_scale_bar(self, dwg, svg_width: float, svg_height: float, margin: float):
        """商用グレードスケールバー追加"""
        # スケールバー仕様
        bar_length_mm = 50.0  # 5cm
        bar_length_px = bar_length_mm * self.scale_factor
        
        # 最小サイズを保証
        bar_length_px = max(bar_length_px, 100)
        
        # 配置位置
        bar_x = margin
        bar_y = svg_height - margin - 50
        
        # スケールバー本体
        dwg.add(dwg.line(start=(bar_x, bar_y), end=(bar_x + bar_length_px, bar_y),
                        stroke='black', stroke_width=3))
        
        # 目盛り
        dwg.add(dwg.line(start=(bar_x, bar_y - 8), end=(bar_x, bar_y + 8),
                        stroke='black', stroke_width=2))
        dwg.add(dwg.line(start=(bar_x + bar_length_px, bar_y - 8), 
                        end=(bar_x + bar_length_px, bar_y + 8),
                        stroke='black', stroke_width=2))
        
        # ラベル
        scale_text = f"{bar_length_mm:.0f} mm (Scale: {self.scale_factor:.2f})"
        dwg.add(dwg.text(scale_text, insert=(bar_x + bar_length_px/2, bar_y - 15),
                        text_anchor="middle", class_="scale-text"))

    def _add_technical_notes(self, dwg, svg_width: float, svg_height: float, margin: float):
        """技術注記・凡例追加"""
        notes_x = svg_width - 300
        notes_y = svg_height - margin - 80
        
        notes = [
            "Legend:",
            "━━━ Cut line (solid)",
            "┅┅┅ Fold line (dashed)",
            "┄┄┄ Tab (glue area)"
        ]
        
        for i, note in enumerate(notes):
            dwg.add(dwg.text(note, insert=(notes_x, notes_y + i * 20), class_="note-text"))

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
            
            # 1. BREPトポロジ解析
            self.analyze_brep_topology()
            
            # 2. 展開可能面のグルーピング
            self.group_faces_for_unfolding(request.max_faces)
            
            # 3. 各グループの2D展開
            unfolded_groups = self.unfold_face_groups()
            
            # 4. グループ配置最適化
            placed_groups = self.layout_unfolded_groups(unfolded_groups)
            
            # 5. SVG出力
            svg_path = self.export_to_svg(placed_groups, output_path)
            
            # 処理統計更新
            end_time = time.time()
            self.stats["processing_time"] = end_time - start_time
            self.stats["unfoldable_faces"] = sum(len(group["polygons"]) for group in placed_groups)
            
            return svg_path, self.stats
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValueError(f"BREP展開図生成エラー: {str(e)}")