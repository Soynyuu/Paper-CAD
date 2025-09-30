import math
import numpy as np
from typing import List, Dict, Optional, Tuple
from scipy.spatial import ConvexHull

from config import OCCT_AVAILABLE

if OCCT_AVAILABLE:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone


class UnfoldEngine:
    """
    展開処理エンジン - 面の展開と配置を担当する独立したクラス
    """
    
    def __init__(self, scale_factor: float = 10.0, tab_width: float = 5.0):
        """
        初期化
        
        Args:
            scale_factor: スケール倍率
            tab_width: タブの幅
        """
        self.scale_factor = scale_factor
        self.tab_width = tab_width
        
        # 展開対象データへの参照
        self.faces_data = None
        self.edges_data = None
        
        # 展開グループ
        self.unfold_groups: List[List[int]] = []
    
    def set_geometry_data(self, faces_data: List[Dict], edges_data: List[Dict]):
        """
        幾何学データを設定
        
        Args:
            faces_data: 面データのリスト
            edges_data: エッジデータのリスト
        """
        self.faces_data = faces_data
        self.edges_data = edges_data
    
    def group_faces_for_unfolding(self, max_faces: int = 20) -> List[List[int]]:
        """
        展開可能な面をグループ化。
        立方体のような単純な形状では全ての面を個別に展開。
        
        Args:
            max_faces: 最大面数
        
        Returns:
            List[List[int]]: 展開グループのリスト
        """
        if self.faces_data is None:
            raise ValueError("faces_dataが設定されていません")
        
        unfoldable_faces = [i for i, face in enumerate(self.faces_data) if face["unfoldable"]]
        
        if not unfoldable_faces:
            print("展開可能な面がありません")
            return []
        
        print(f"展開可能な面: {len(unfoldable_faces)}個")
        
        # 立方体のような単純な形状では、各面を個別のグループとして扱う
        groups = []
        
        for face_idx in unfoldable_faces:
            # 各面を個別のグループとして追加
            groups.append([face_idx])
            print(f"面{face_idx}をグループ{len(groups)-1}に追加")
        
        self.unfold_groups = groups
        print(f"作成されたグループ数: {len(groups)}")
        return groups
    
    def unfold_face_groups(self) -> List[Dict]:
        """
        各面グループを2D展開図に変換。
        曲面タイプに応じた最適な展開アルゴリズムを適用。
        
        Returns:
            List[Dict]: 展開済みグループのリスト
        """
        if self.faces_data is None:
            raise ValueError("faces_dataが設定されていません")
        
        unfolded_groups = []
        
        print(f"=== 面グループ展開開始 ===")
        print(f"グループ数: {len(self.unfold_groups)}")
        
        for group_idx, face_indices in enumerate(self.unfold_groups):
            print(f"\n--- グループ {group_idx} ---")
            print(f"面数: {len(face_indices)}")
            print(f"面インデックス: {face_indices}")
            
            # 各面の詳細情報を表示
            for i, face_idx in enumerate(face_indices):
                if face_idx < len(self.faces_data):
                    face_data = self.faces_data[face_idx]
                    print(f"  面{i}(idx={face_idx}): {face_data['surface_type']}, 面積={face_data.get('area', 'N/A')}")
                else:
                    print(f"  面{i}(idx={face_idx}): インデックスが範囲外")
            
            try:
                group_result = self._unfold_single_group(group_idx, face_indices)
                if group_result:
                    print(f"  → 展開成功: {len(group_result.get('polygons', []))}個のポリゴン")
                    unfolded_groups.append(group_result)
                else:
                    print(f"  → 展開失敗: 結果がNone")
            except Exception as e:
                print(f"  → グループ{group_idx}の展開でエラー: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n=== 展開完了 ===")
        print(f"成功したグループ数: {len(unfolded_groups)}")
        return unfolded_groups
    
    def _unfold_single_group(self, group_idx: int, face_indices: List[int]) -> Optional[Dict]:
        """
        単一面グループの展開処理。
        
        Args:
            group_idx: グループインデックス
            face_indices: 面インデックスのリスト
        
        Returns:
            Optional[Dict]: 展開結果
        """
        if not face_indices:
            print(f"    グループ{group_idx}: 面インデックスが空")
            return None
            
        primary_face = self.faces_data[face_indices[0]]
        surface_type = primary_face["surface_type"]
        
        print(f"    グループ{group_idx}: 主面タイプ={surface_type}")
        
        try:
            if surface_type == "plane":
                print(f"    → 平面グループとして展開")
                return self._unfold_planar_group(group_idx, face_indices)
            elif surface_type == "cylinder":
                print(f"    → 円筒グループとして展開")
                return self._unfold_cylindrical_group(group_idx, face_indices)
            elif surface_type == "cone":
                print(f"    → 円錐グループとして展開")
                return self._unfold_conical_group(group_idx, face_indices)
            else:
                print(f"    → 未対応の曲面タイプ: {surface_type}")
                return None
                
        except Exception as e:
            print(f"    → グループ{group_idx}展開エラー: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _unfold_planar_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        平面グループの展開（面の正確な形状に基づく）。
        
        Args:
            group_idx: グループインデックス
            face_indices: 面インデックスのリスト
        
        Returns:
            Dict: 展開結果
        """
        polygons = []
        
        print(f"      平面グループ{group_idx}を展開中...")
        
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            
            # 平面情報を取得
            normal = np.array(face_data["plane_normal"])
            origin = np.array(face_data["plane_origin"])
            
            print(f"        面{face_idx}: 法線={normal}, 原点={origin}")
            
            # 面の正確な境界形状を取得
            face_polygons = self._extract_face_2d_shape(face_idx, normal, origin)
            print(f"        面{face_idx}: {len(face_polygons) if face_polygons else 0}個の2D形状を抽出")
            
            if face_polygons:
                polygons.extend(face_polygons)
        
        print(f"      平面グループ{group_idx}: 合計{len(polygons)}個のポリゴン")
        
        # 面番号のマッピングを追加
        face_numbers = []
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            face_numbers.append(face_data.get("face_number", face_idx + 1))
        
        return {
            "group_index": group_idx,
            "surface_type": "plane",
            "polygons": polygons,
            "face_indices": face_indices,  # 元の面インデックス
            "face_numbers": face_numbers,  # ユーザー向け面番号
            "tabs": [],
            "fold_lines": [],
            "cut_lines": []
        }
    
    def _unfold_cylindrical_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        円筒面グループの展開（正確な円筒座標→直交座標変換）。
        円筒面と円形の蓋を組み合わせて、実際に組み立て可能な展開図を生成。
        
        Args:
            group_idx: グループインデックス
            face_indices: 面インデックスのリスト
        
        Returns:
            Dict: 展開結果
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
        
        # 面番号のマッピングを追加
        face_numbers = []
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            face_numbers.append(face_data.get("face_number", face_idx + 1))
        
        return {
            "group_index": group_idx,
            "surface_type": "cylinder",
            "polygons": polygons,
            "face_indices": face_indices,
            "face_numbers": face_numbers,
            "tabs": [],
            "unfold_method": "cylindrical_unwrap_with_caps"
        }
    
    def _unfold_conical_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        円錐面グループの展開（円錐展開図）。
        
        Args:
            group_idx: グループインデックス
            face_indices: 面インデックスのリスト
        
        Returns:
            Dict: 展開結果
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
        
        # 面番号のマッピングを追加
        face_numbers = []
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            face_numbers.append(face_data.get("face_number", face_idx + 1))
        
        return {
            "group_index": group_idx,
            "surface_type": "cone",
            "polygons": polygons,
            "face_indices": face_indices,
            "face_numbers": face_numbers,
            "tabs": [],
            "unfold_method": "conical_unwrap"
        }
    
    def _extract_face_2d_shape(self, face_idx: int, normal: np.ndarray, origin: np.ndarray) -> List[List[Tuple[float, float]]]:
        """
        面の正確な2D形状を抽出（外形線・内形線を考慮）。
        
        Args:
            face_idx: 面インデックス
            normal: 法線ベクトル
            origin: 原点
        
        Returns:
            List[List[Tuple[float, float]]]: 2Dポリゴンのリスト
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
    
    def _project_points_to_plane_accurate(self, points_3d: List[Tuple[float, float, float]], 
                                         normal: np.ndarray, origin: np.ndarray) -> List[Tuple[float, float]]:
        """
        3D点群を平面に正確に投影（直交座標系を構築）。
        
        Args:
            points_3d: 3D点群
            normal: 法線ベクトル
            origin: 原点
        
        Returns:
            List[Tuple[float, float]]: 投影された2D点群
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
    
    def _simplify_boundary_polygon(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        境界線ポリゴンを簡略化（形状に応じて適切な点数に削減）。
        
        Args:
            points_2d: 2D点群
        
        Returns:
            List[Tuple[float, float]]: 簡略化された2D点群
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
        
        # 六角形以上の多角形を検出
        detected_corners = self._detect_polygon_corners(cleaned_points)
        if detected_corners > 5:
            result = self._extract_corners_by_angle(cleaned_points, detected_corners)
            print(f"{len(result)}点（{detected_corners}角形）")
            return result
        
        # その他の多角形は適度に間引く
        result = self._thin_out_points(cleaned_points, max_points=12)
        print(f"{len(result)}点（一般多角形）")
        return result
    
    def _remove_duplicate_points_2d(self, points_2d: List[Tuple[float, float]], tolerance: float = 1e-6) -> List[Tuple[float, float]]:
        """
        重複点を除去（2D点用）。
        
        Args:
            points_2d: 2D点群
            tolerance: 許容誤差
        
        Returns:
            List[Tuple[float, float]]: 重複除去後の2D点群
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
        
        Args:
            points_2d: 2D点群
        
        Returns:
            List[Tuple[float, float]]: 反時計回りの2D点群
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
    
    def _is_triangular_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が三角形かどうかを判定。
        
        Args:
            points_2d: 2D点群
        
        Returns:
            bool: 三角形の場合True
        """
        if len(points_2d) < 6:  # 最低でも6点は必要
            return False
        
        # 凸包を計算して3点になるかチェック
        try:
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点が3個なら三角形
            return len(hull.vertices) == 3
        except:
            return False
    
    def _extract_triangle_corners(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点群から三角形の3つの角を抽出。
        
        Args:
            points_2d: 2D点群
        
        Returns:
            List[Tuple[float, float]]: 三角形の角
        """
        try:
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
    
    def _is_rectangular_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が四角形（正方形・長方形）かどうかを判定。
        
        Args:
            points_2d: 2D点群
        
        Returns:
            bool: 四角形の場合True
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
        
        Args:
            points_2d: 2D点群
        
        Returns:
            List[Tuple[float, float]]: 四角形の角
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
    
    def _sort_points_clockwise(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点を時計回りに並び替え。
        
        Args:
            points: 2D点群
        
        Returns:
            List[Tuple[float, float]]: 時計回りの2D点群
        """
        # 重心を計算
        center_x = sum(p[0] for p in points) / len(points)
        center_y = sum(p[1] for p in points) / len(points)
        
        # 角度でソート
        def angle_from_center(point):
            return math.atan2(point[1] - center_y, point[0] - center_x)
        
        sorted_points = sorted(points, key=angle_from_center)
        return sorted_points
    
    def _extract_corners_by_angle(self, points_2d: List[Tuple[float, float]], num_corners: int) -> List[Tuple[float, float]]:
        """
        角度変化を基に多角形の角を抽出。
        
        Args:
            points_2d: 2D点群
            num_corners: 抽出する角の数
        
        Returns:
            List[Tuple[float, float]]: 抽出された角の点群
        """
        if len(points_2d) < num_corners:
            return points_2d
        
        # 重心を計算
        center_x = sum(p[0] for p in points_2d) / len(points_2d)
        center_y = sum(p[1] for p in points_2d) / len(points_2d)
        
        # 各点の角度を計算
        angles_with_points = []
        for point in points_2d:
            angle = math.atan2(point[1] - center_y, point[0] - center_x)
            # 角度を正の値に正規化
            if angle < 0:
                angle += 2 * math.pi
            angles_with_points.append((angle, point))
        
        # 角度でソート
        angles_with_points.sort(key=lambda x: x[0])
        
        # 等間隔で角を選択
        corners = []
        step = len(angles_with_points) // num_corners
        for i in range(num_corners):
            idx = (i * step) % len(angles_with_points)
            corners.append(angles_with_points[idx][1])
        
        # 閉じた多角形にする
        if corners and corners[0] != corners[-1]:
            corners.append(corners[0])
            
        return corners
    
    def _detect_polygon_corners(self, points_2d: List[Tuple[float, float]]) -> int:
        """
        点群から多角形の角数を検出。
        
        Args:
            points_2d: 2D点群
        
        Returns:
            int: 検出された角数（3-12の範囲）
        """
        if len(points_2d) < 6:
            return 3
        
        try:
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点数が角数
            num_corners = len(hull.vertices)
            
            # 3-12角形の範囲に制限
            return max(3, min(12, num_corners))
        except:
            # フォールバック：点数から推定
            estimated_corners = max(3, min(12, len(points_2d) // 5))
            return estimated_corners
    
    def _is_pentagonal_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が五角形かどうかを判定。
        
        Args:
            points_2d: 2D点群
        
        Returns:
            bool: 五角形の場合True
        """
        if len(points_2d) < 10:  # 最低でも10点は必要
            return False
        
        # 凸包を計算して5点になるかチェック
        try:
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点が5個なら五角形
            return len(hull.vertices) == 5
        except:
            return False
    
    def _extract_pentagon_corners(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点群から五角形の5つの角を抽出。
        
        Args:
            points_2d: 2D点群
        
        Returns:
            List[Tuple[float, float]]: 五角形の角
        """
        try:
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            if len(hull.vertices) == 5:
                # 凸包の頂点を時計回りに並び替え
                pentagon_corners = [tuple(points_array[i]) for i in hull.vertices]
                pentagon_corners = self._sort_points_clockwise(pentagon_corners)
                # 閉じた五角形にする
                pentagon_corners.append(pentagon_corners[0])
                return pentagon_corners
            else:
                # フォールバック：角度ベースで5つの角を抽出
                return self._extract_corners_by_angle(points_2d, 5)
        except:
            # エラーの場合は元の点をそのまま返す
            return points_2d
    
    def _thin_out_points(self, points_2d: List[Tuple[float, float]], max_points: int = 12) -> List[Tuple[float, float]]:
        """
        点群を適度に間引く。
        
        Args:
            points_2d: 2D点群
            max_points: 最大点数
        
        Returns:
            List[Tuple[float, float]]: 間引いた2D点群
        """
        if len(points_2d) <= max_points:
            return points_2d
            
        # 等間隔で点を選択
        step = len(points_2d) // max_points
        return [points_2d[i] for i in range(0, len(points_2d), step)]
    
    def _extract_cylindrical_face_2d(self, face_idx: int, axis: np.ndarray, center: np.ndarray, 
                                    radius: float) -> List[List[Tuple[float, float]]]:
        """
        円筒面の正確な2D形状を抽出。
        
        Args:
            face_idx: 面インデックス
            axis: 軸ベクトル
            center: 中心点
            radius: 半径
        
        Returns:
            List[List[Tuple[float, float]]]: 2Dポリゴンのリスト
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
        
        Args:
            points_3d: 3D点群
            axis: 軸ベクトル
            center: 中心点
            radius: 半径
        
        Returns:
            List[Tuple[float, float]]: 展開された2D点群
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
    
    def _extract_conical_face_2d(self, face_idx: int, apex: np.ndarray, axis: np.ndarray, 
                                radius: float, semi_angle: float) -> List[List[Tuple[float, float]]]:
        """
        円錐面の正確な2D形状を抽出。
        
        Args:
            face_idx: 面インデックス
            apex: 頂点
            axis: 軸ベクトル
            radius: 半径
            semi_angle: 半角
        
        Returns:
            List[List[Tuple[float, float]]]: 2Dポリゴンのリスト
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
        
        Args:
            points_3d: 3D点群
            apex: 頂点
            axis: 軸ベクトル
            radius: 半径
            semi_angle: 半角
        
        Returns:
            List[Tuple[float, float]]: 展開された2D点群
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
    
    def _is_circular_face(self, face_data: Dict) -> bool:
        """
        平面が円形かどうかを判定。
        
        Args:
            face_data: 面データ
        
        Returns:
            bool: 円形の場合True
        """
        # 仮実装：常にFalseを返す
        return False
    
    def _extract_circular_face_2d(self, face_data: Dict) -> List[Tuple[float, float]]:
        """
        円形の面を2D形状として抽出。
        
        Args:
            face_data: 面データ
        
        Returns:
            List[Tuple[float, float]]: 2D形状
        """
        # 仮実装：空リストを返す
        return []
    
    def _generate_cylindrical_tabs(self, cylindrical_faces: List[int], planar_faces: List[int]) -> List[List[Tuple[float, float]]]:
        """
        円筒面グループ用のタブを生成。
        
        Args:
            cylindrical_faces: 円筒面のインデックスリスト
            planar_faces: 平面のインデックスリスト
        
        Returns:
            List[List[Tuple[float, float]]]: タブのリスト
        """
        # 仮実装：空リストを返す
        return []
    
    def _generate_tabs_for_group(self, face_indices: List[int]) -> List[List[Tuple[float, float]]]:
        """
        面グループ間の接着タブを生成。
        隣接エッジ情報から適切なタブ形状を自動生成。
        
        Args:
            face_indices: 面インデックスのリスト
        
        Returns:
            List[List[Tuple[float, float]]]: タブのリスト
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
    
    def _expand_face_group(self, current_group: List[int], used_faces: set, 
                          available_faces: List[int], max_group_size: int = 5):
        """
        面グループを隣接面で拡張。
        
        Args:
            current_group: 現在のグループ
            used_faces: 使用済みの面のセット
            available_faces: 利用可能な面のリスト
            max_group_size: 最大グループサイズ
        """
        if len(current_group) >= max_group_size:
            return
            
        # 現在のグループの最後の面に隣接する面を探す
        last_face_idx = current_group[-1]
        last_face = self.faces_data[last_face_idx]
        
        # 同一タイプの未使用面を優先的に探す
        for face_idx in available_faces:
            if (face_idx not in used_faces and 
                face_idx not in current_group and
                self.faces_data[face_idx]["surface_type"] == last_face["surface_type"]):
                
                # 隣接判定（簡易版 - 重心距離による）
                if self._are_faces_adjacent(last_face_idx, face_idx):
                    current_group.append(face_idx)
                    used_faces.add(face_idx)
                    
                    if len(current_group) < max_group_size:
                        self._expand_face_group(current_group, used_faces, available_faces, max_group_size)
                    break
    
    def _are_faces_adjacent(self, face_idx1: int, face_idx2: int, threshold: float = 10.0) -> bool:
        """
        2つの面が隣接しているか判定（簡易版）。
        実際の商用実装では共有エッジの存在を正確に判定する必要がある。
        
        Args:
            face_idx1: 面1のインデックス
            face_idx2: 面2のインデックス
            threshold: 距離の閾値
        
        Returns:
            bool: 隣接している場合True
        """
        centroid1 = np.array(self.faces_data[face_idx1]["centroid"])
        centroid2 = np.array(self.faces_data[face_idx2]["centroid"])
        distance = np.linalg.norm(centroid1 - centroid2)
        return distance < threshold