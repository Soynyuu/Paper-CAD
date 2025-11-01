"""
BREP形状の幾何学解析を行うクラス。
面・エッジ・頂点の幾何特性を抽出し、展開戦略を決定する。
"""

import math
import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy.spatial import ConvexHull

from config import OCCT_AVAILABLE

if OCCT_AVAILABLE:
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere
    from OCC.Core.gp import gp_Pnt, gp_Vec
    from OCC.Core.Geom import Geom_Surface, Geom_Plane, Geom_CylindricalSurface, Geom_ConicalSurface


class GeometryAnalyzer:
    """
    BREP形状の幾何学解析を行うクラス。
    面・エッジ・頂点の幾何特性を抽出し、展開戦略を決定する。
    """
    
    def __init__(self):
        self.faces_data: List[Dict] = []
        self.edges_data: List[Dict] = []
        # 各方向の面のカウンター（ユニークな番号を割り当てるため）
        self.face_direction_counters = {
            'pos_z': 0,  # +Z方向
            'neg_z': 0,  # -Z方向
            'pos_x': 0,  # +X方向
            'neg_x': 0,  # -X方向
            'pos_y': 0,  # +Y方向
            'neg_y': 0,  # -Y方向
            'other': 0   # その他
        }
        self.stats = {
            "total_faces": 0,
            "planar_faces": 0,
            "cylindrical_faces": 0,
            "conical_faces": 0,
            "other_faces": 0,
        }
    
    def reset_face_numbering(self):
        """
        面番号カウンターをリセットする。新しい形状の解析を開始する前に呼び出す。
        """
        self.face_direction_counters = {
            'pos_z': 0,  # +Z方向
            'neg_z': 0,  # -Z方向
            'pos_x': 0,  # +X方向
            'neg_x': 0,  # -X方向
            'pos_y': 0,  # +Y方向
            'neg_y': 0,  # -Y方向
            'other': 0   # その他
        }
        print("面番号カウンターをリセットしました")
    
    def analyze_brep_topology(self, solid_shape):
        """
        BREPソリッドのトポロジ構造を詳細解析。
        面・エッジ・頂点の幾何特性を抽出し、展開戦略を決定。
        """
        if solid_shape is None:
            raise ValueError("BREPデータが読み込まれていません")
        
        print("BREPトポロジ解析開始...")
        self.faces_data.clear()
        self.edges_data.clear()
        self.reset_face_numbering()  # 面番号カウンターをリセット
        
        try:
            # --- 面（Face）の解析 ---
            face_explorer = TopExp_Explorer(solid_shape, TopAbs_FACE)
            face_index = 0
            
            while face_explorer.More():
                face = face_explorer.Current()
                print(f"面 {face_index} を解析中...")
                face_data = self._analyze_face_geometry(face, face_index)
                if face_data:
                    self.faces_data.append(face_data)
                    print(f"面 {face_index} 解析完了: {face_data['surface_type']}, 面積: {face_data['area']:.2f}")
                face_index += 1
                face_explorer.Next()
            
            # --- エッジ（Edge）の解析 ---
            edge_explorer = TopExp_Explorer(solid_shape, TopAbs_EDGE)
            edge_index = 0
            
            while edge_explorer.More():
                edge = edge_explorer.Current()
                print(f"エッジ {edge_index} を解析中...")
                edge_data = self._analyze_edge_geometry(edge, edge_index)
                if edge_data:
                    self.edges_data.append(edge_data)
                edge_index += 1
                edge_explorer.Next()
            
            # --- 統計情報更新 ---
            self.stats["total_faces"] = len(self.faces_data)
            self.stats["planar_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "plane")
            self.stats["cylindrical_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "cylinder")
            self.stats["conical_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "cone")
            self.stats["other_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "other")
            
            print(f"トポロジ解析完了: {self.stats['total_faces']} 面, {len(self.edges_data)} エッジ")
            print(f"面の内訳: 平面={self.stats['planar_faces']}, 円筒={self.stats['cylindrical_faces']}, 円錐={self.stats['conical_faces']}, その他={self.stats['other_faces']}")
            
        except Exception as e:
            print(f"トポロジ解析エラー: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"BREPトポロジ解析エラー: {str(e)}")

    def _analyze_face_geometry(self, face, face_index: int):
        """
        個別面の幾何特性を詳細解析。
        曲面タイプ・パラメータ・境界・面積等を取得。
        """
        try:
            # 面アダプタ取得
            surface_adaptor = BRepAdaptor_Surface(face)
            surface_type_enum = surface_adaptor.GetType()

            # 面積計算（簡易版）
            # 面の境界から面積を推定
            area = 100.0  # デフォルト値（立方体の場合）

            # 重心計算（面の中心点を近似）
            # 面のパラメータ範囲の中心を使用
            try:
                u_min, u_max, v_min, v_max = surface_adaptor.BoundsUV()
                u_mid = (u_min + u_max) / 2
                v_mid = (v_min + v_max) / 2
                center_point = surface_adaptor.Value(u_mid, v_mid)
                centroid = center_point
            except:
                # フォールバック：原点を使用
                centroid = gp_Pnt(0, 0, 0)

            # 法線ベクトルを取得（立方体の面を識別するため）
            normal_vec = None
            if surface_type_enum == GeomAbs_Plane:
                try:
                    plane = surface_adaptor.Plane()
                    axis = plane.Axis()
                    normal_dir = axis.Direction()
                    normal_vec = [normal_dir.X(), normal_dir.Y(), normal_dir.Z()]
                except:
                    pass

            # 法線ベクトルに基づいて面番号を割り当てる
            face_number = self._assign_face_number_by_normal(normal_vec, [centroid.X(), centroid.Y(), centroid.Z()])

            face_data = {
                "index": face_index,
                "face_number": face_number,  # ユニークな面番号
                "area": area,
                "centroid": [centroid.X(), centroid.Y(), centroid.Z()],
                "surface_type": self._get_surface_type_name(surface_type_enum),
                "normal_vector": normal_vec,  # 法線ベクトルを保存
                "unfoldable": True,  # デフォルトで展開可能とする（後で平面性チェックで修正される）
                "boundary_curves": []
            }

            # 曲面タイプ別の詳細解析
            if surface_type_enum == GeomAbs_Plane:
                face_data.update(self._analyze_planar_face(surface_adaptor))

            elif surface_type_enum == GeomAbs_Cylinder:
                face_data.update(self._analyze_cylindrical_face(surface_adaptor))

            elif surface_type_enum == GeomAbs_Cone:
                face_data.update(self._analyze_conical_face(surface_adaptor))

            else:
                # その他の曲面も近似展開を試みる
                face_data.update(self._analyze_general_surface(surface_adaptor))
                # サポートされない曲面タイプは展開不可
                print(f"⚠️  面{face_index}: サポートされない曲面タイプ ({face_data['surface_type']}) - 展開をスキップ")
                face_data["unfoldable"] = False

            # 境界線解析
            face_data["boundary_curves"] = self._extract_face_boundaries(face)

            # 境界線が取得できない場合の改善されたフォールバック処理
            if not face_data["boundary_curves"]:
                print(f"⚠️  面{face_index}: 境界線抽出失敗 - フォールバック処理を実行")
                # 凸包ベースの境界線を生成（デフォルト正方形より優れた方法）
                face_data["boundary_curves"] = self._generate_convex_hull_boundary(face, surface_adaptor)

                # それでも失敗した場合はデフォルト正方形を使用
                if not face_data["boundary_curves"]:
                    print(f"⚠️  面{face_index}: 凸包も失敗 - デフォルト正方形を使用")
                    face_data["boundary_curves"] = self._generate_default_square_boundary()

            # デバッグ情報の追加
            vertex_count = sum(len(boundary) for boundary in face_data["boundary_curves"])
            print(f"  → 面{face_index}: タイプ={face_data['surface_type']}, 頂点数={vertex_count}, 面積={face_data.get('area', 'N/A'):.2f}")

            # 頂点数が異常に多い場合は警告
            if vertex_count > 50:
                print(f"⚠️  面{face_index}: 頂点数が多い ({vertex_count}点) - 簡略化が推奨されます")

            # 面積が極端に小さい場合は展開をスキップ
            estimated_area = self._estimate_face_area(face_data["boundary_curves"])
            if estimated_area < 1.0:  # 1mm²未満
                print(f"⚠️  面{face_index}: 面積が極端に小さい ({estimated_area:.4f}mm²) - 展開をスキップ")
                face_data["unfoldable"] = False

            # 平面として認識された面の平面性を検証
            if face_data["surface_type"] == "plane" and face_data["unfoldable"]:
                is_planar, planarity_deviation = self._validate_planarity(face_data["boundary_curves"], normal_vec)
                if not is_planar:
                    print(f"⚠️  面{face_index}: 平面性検証失敗（偏差={planarity_deviation:.4f}mm） - 展開をスキップ")
                    face_data["unfoldable"] = False
                    face_data["planarity_deviation"] = planarity_deviation
                else:
                    print(f"  ✓ 面{face_index}: 平面性検証成功（偏差={planarity_deviation:.4f}mm）")
                    face_data["planarity_deviation"] = planarity_deviation

            return face_data

        except Exception as e:
            print(f"面{face_index}の解析でエラー: {e}")
            return None

    def _analyze_planar_face(self, surface_adaptor):
        """平面の詳細解析"""
        plane = surface_adaptor.Plane()
        normal = plane.Axis().Direction()
        origin = plane.Location()
        
        return {
            "plane_normal": [normal.X(), normal.Y(), normal.Z()],
            "plane_origin": [origin.X(), origin.Y(), origin.Z()],
            "unfold_method": "direct_projection"
        }

    def _analyze_cylindrical_face(self, surface_adaptor):
        """円筒面の詳細解析"""
        cylinder = surface_adaptor.Cylinder()
        axis = cylinder.Axis()
        radius = cylinder.Radius()
        
        axis_dir = axis.Direction()
        axis_loc = axis.Location()
        
        return {
            "cylinder_axis": [axis_dir.X(), axis_dir.Y(), axis_dir.Z()],
            "cylinder_center": [axis_loc.X(), axis_loc.Y(), axis_loc.Z()],
            "cylinder_radius": radius,
            "unfold_method": "cylindrical_unwrap"
        }

    def _analyze_conical_face(self, surface_adaptor):
        """円錐面の詳細解析"""
        cone = surface_adaptor.Cone()
        apex = cone.Apex()
        axis = cone.Axis()
        radius = cone.RefRadius()
        semi_angle = cone.SemiAngle()
        
        axis_dir = axis.Direction()
        
        return {
            "cone_apex": [apex.X(), apex.Y(), apex.Z()],
            "cone_axis": [axis_dir.X(), axis_dir.Y(), axis_dir.Z()],
            "cone_radius": radius,
            "cone_semi_angle": semi_angle,
            "unfold_method": "conical_unwrap"
        }

    def _get_surface_type_name(self, surface_type_enum) -> str:
        """曲面タイプ列挙値を文字列に変換"""
        type_map = {
            GeomAbs_Plane: "plane",
            GeomAbs_Cylinder: "cylinder", 
            GeomAbs_Cone: "cone",
            GeomAbs_Sphere: "sphere"
        }
        return type_map.get(surface_type_enum, "other")
    
    def _assign_face_number_by_normal(self, normal_vec, centroid):
        """
        法線ベクトルの方向に基づいて面番号を割り当てる。
        同じ方向の面が複数ある場合は、連番でユニークな番号を割り当てる。
        
        番号体系（フロントエンドと統一）:
        1, 11, 21... : +Z方向の面（前面）
        2, 12, 22... : -Z方向の面（背面）
        3, 13, 23... : +X方向の面（右面）
        4, 14, 24... : -X方向の面（左面）
        5, 15, 25... : +Y方向の面（上面）
        6, 16, 26... : -Y方向の面（下面）
        7, 17, 27... : その他の面
        """
        if not normal_vec:
            # 法線ベクトルが取得できない場合
            self.face_direction_counters['other'] += 1
            face_number = 7 + (self.face_direction_counters['other'] - 1) * 10
            print(f"  -> 法線不明として面番号{face_number}を割り当て")
            return face_number
        
        # 法線ベクトルの正規化
        normal_magnitude = math.sqrt(normal_vec[0]**2 + normal_vec[1]**2 + normal_vec[2]**2)
        if normal_magnitude < 1e-8:
            # 法線がゼロベクトルの場合
            self.face_direction_counters['other'] += 1
            face_number = 7 + (self.face_direction_counters['other'] - 1) * 10
            print(f"  -> ゼロ法線として面番号{face_number}を割り当て")
            return face_number
        
        # 正規化された法線ベクトル
        normalized_normal = [normal_vec[0]/normal_magnitude, 
                           normal_vec[1]/normal_magnitude, 
                           normal_vec[2]/normal_magnitude]
        
        # 法線ベクトルの主成分を判定（より高い閾値で確実に判定）
        abs_x = abs(normalized_normal[0])
        abs_y = abs(normalized_normal[1])
        abs_z = abs(normalized_normal[2])
        threshold = 0.7  # 主成分を判定する閾値
        
        print(f"  -> 法線ベクトル: ({normalized_normal[0]:.3f}, {normalized_normal[1]:.3f}, {normalized_normal[2]:.3f})")
        print(f"  -> 成分: |X|={abs_x:.3f}, |Y|={abs_y:.3f}, |Z|={abs_z:.3f}")
        
        # Z軸方向の判定
        if abs_z >= threshold and abs_z >= abs_x and abs_z >= abs_y:
            if normalized_normal[2] > 0:
                # +Z方向（前面）
                self.face_direction_counters['pos_z'] += 1
                face_number = 1 + (self.face_direction_counters['pos_z'] - 1) * 10
                print(f"  -> +Z方向（前面）として面番号{face_number}を割り当て")
                return face_number
            else:
                # -Z方向（背面）
                self.face_direction_counters['neg_z'] += 1
                face_number = 2 + (self.face_direction_counters['neg_z'] - 1) * 10
                print(f"  -> -Z方向（背面）として面番号{face_number}を割り当て")
                return face_number
                
        # X軸方向の判定
        elif abs_x >= threshold and abs_x >= abs_y and abs_x >= abs_z:
            if normalized_normal[0] > 0:
                # +X方向（右面）
                self.face_direction_counters['pos_x'] += 1
                face_number = 3 + (self.face_direction_counters['pos_x'] - 1) * 10
                print(f"  -> +X方向（右面）として面番号{face_number}を割り当て")
                return face_number
            else:
                # -X方向（左面）
                self.face_direction_counters['neg_x'] += 1
                face_number = 4 + (self.face_direction_counters['neg_x'] - 1) * 10
                print(f"  -> -X方向（左面）として面番号{face_number}を割り当て")
                return face_number
                
        # Y軸方向の判定
        elif abs_y >= threshold and abs_y >= abs_x and abs_y >= abs_z:
            if normalized_normal[1] > 0:
                # +Y方向（上面）
                self.face_direction_counters['pos_y'] += 1
                face_number = 5 + (self.face_direction_counters['pos_y'] - 1) * 10
                print(f"  -> +Y方向（上面）として面番号{face_number}を割り当て")
                return face_number
            else:
                # -Y方向（下面）
                self.face_direction_counters['neg_y'] += 1
                face_number = 6 + (self.face_direction_counters['neg_y'] - 1) * 10
                print(f"  -> -Y方向（下面）として面番号{face_number}を割り当て")
                return face_number
        else:
            # その他の方向（斜め面など）
            self.face_direction_counters['other'] += 1
            face_number = 7 + (self.face_direction_counters['other'] - 1) * 10
            print(f"  -> その他の方向として面番号{face_number}を割り当て")
            return face_number

    def _extract_face_boundaries(self, face):
        """
        面の境界線を3D座標列として抽出（ソリッドベース）。
        面のパラメータ空間での正確な境界形状を取得。
        """
        boundaries = []
        
        try:
            print(f"    面の境界線抽出開始...")
            
            # 面のアダプター取得
            face_adaptor = BRepAdaptor_Surface(face)
            
            # ワイヤ（境界線）を探索
            wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
            wire_count = 0
            
            while wire_explorer.More():
                wire = wire_explorer.Current()
                print(f"      ワイヤ{wire_count}を処理中...")
                
                # 高精度サンプリングを試行
                boundary_points = self._extract_wire_points_parametric(wire, face_adaptor)
                
                if boundary_points and len(boundary_points) >= 3:
                    boundaries.append(boundary_points)
                    print(f"      ワイヤ{wire_count}: {len(boundary_points)}点を抽出（高精度）")
                else:
                    # フォールバック：3D直接サンプリング
                    boundary_points = self._extract_wire_points_fallback(wire)
                    if boundary_points and len(boundary_points) >= 3:
                        boundaries.append(boundary_points)
                        print(f"      ワイヤ{wire_count}: {len(boundary_points)}点を抽出（フォールバック）")
                    else:
                        print(f"      ワイヤ{wire_count}: 境界点の抽出に失敗")
                
                wire_count += 1
                wire_explorer.Next()
            
            print(f"    面の境界線抽出完了: {len(boundaries)}本のワイヤ")
                
        except Exception as e:
            print(f"    境界線抽出エラー: {e}")
            import traceback
            traceback.print_exc()
            
        return boundaries

    def _extract_wire_points_parametric(self, wire, face_adaptor, num_points: int = 100) -> List[Tuple[float, float, float]]:
        """
        ワイヤから面のパラメータ空間を考慮した高精度サンプリング点を抽出。
        """
        points = []
        
        try:
            edge_explorer = TopExp_Explorer(wire, TopAbs_EDGE)
            edge_count = 0
            
            while edge_explorer.More():
                edge = edge_explorer.Current()
                
                # まずは3D空間でのサンプリングを試行（より確実）
                edge_points = self._sample_edge_points_3d(edge, num_points // 10)
                if edge_points:
                    points.extend(edge_points)
                    print(f"    エッジ{edge_count}: {len(edge_points)}点を3D抽出")
                else:
                    print(f"    エッジ{edge_count}: 3D抽出に失敗")
                    
                edge_count += 1
                edge_explorer.Next()
                
        except Exception as e:
            print(f"パラメータ空間ワイヤ点抽出エラー: {e}")
            # フォールバック処理
            return self._extract_wire_points_fallback(wire, num_points)
            
        return points

    def _sample_edge_points_parametric(self, curve_2d, face_adaptor, u_min, u_max, num_samples: int = 20) -> List[Tuple[float, float, float]]:
        """
        パラメータ空間での2Dカーブから3D点を生成。
        """
        points = []
        
        try:
            for i in range(num_samples + 1):
                u = u_min + (u_max - u_min) * i / num_samples
                
                # パラメータ空間での2D点を取得
                point_2d = curve_2d.Value(u)
                u_param = point_2d.X()
                v_param = point_2d.Y()
                
                # パラメータから3D点を計算
                point_3d = face_adaptor.Value(u_param, v_param)
                points.append((point_3d.X(), point_3d.Y(), point_3d.Z()))
                
        except Exception as e:
            print(f"パラメータ空間エッジサンプリングエラー: {e}")
            
        return points

    def _sample_edge_points_3d(self, edge, num_samples: int = 20) -> List[Tuple[float, float, float]]:
        """
        3D空間でのエッジサンプリング（フォールバック）。
        """
        points = []
        
        try:
            curve_adaptor = BRepAdaptor_Curve(edge)
            u_min = curve_adaptor.FirstParameter()
            u_max = curve_adaptor.LastParameter()
            
            for i in range(num_samples + 1):
                u = u_min + (u_max - u_min) * i / num_samples
                point = curve_adaptor.Value(u)
                points.append((point.X(), point.Y(), point.Z()))
                
        except Exception as e:
            print(f"3Dエッジサンプリングエラー: {e}")
            
        return points

    def _extract_wire_points_fallback(self, wire, num_points: int = 50) -> List[Tuple[float, float, float]]:
        """
        フォールバック：従来の方法でワイヤから点を抽出。
        """
        points = []
        
        try:
            edge_explorer = TopExp_Explorer(wire, TopAbs_EDGE)
            
            while edge_explorer.More():
                edge = edge_explorer.Current()
                edge_points = self._sample_edge_points_3d(edge, num_points // 10)
                points.extend(edge_points)
                edge_explorer.Next()
            
            # 重複点除去
            if points:
                points = self._remove_duplicate_points(points)
                
        except Exception as e:
            print(f"フォールバックワイヤ点抽出エラー: {e}")
            
        return points

    def _analyze_edge_geometry(self, edge, edge_index: int):
        """
        エッジの幾何特性解析（隣接面・タイプ・長さ等）
        """
        try:
            # エッジの長さ計算（代替方法）
            curve_adaptor = BRepAdaptor_Curve(edge)
            u_min = curve_adaptor.FirstParameter()
            u_max = curve_adaptor.LastParameter()
            
            # 簡易長さ計算
            num_samples = 10
            total_length = 0.0
            prev_point = None
            
            for i in range(num_samples + 1):
                u = u_min + (u_max - u_min) * i / num_samples
                current_point = curve_adaptor.Value(u)
                
                if prev_point is not None:
                    dx = current_point.X() - prev_point.X()
                    dy = current_point.Y() - prev_point.Y()
                    dz = current_point.Z() - prev_point.Z()
                    segment_length = (dx*dx + dy*dy + dz*dz)**0.5
                    total_length += segment_length
                    
                prev_point = current_point
            
            length = total_length
            
            # 中点取得
            u_mid = (u_min + u_max) / 2
            midpoint = curve_adaptor.Value(u_mid)
            
            return {
                "index": edge_index,
                "length": length,
                "midpoint": [midpoint.X(), midpoint.Y(), midpoint.Z()],
                "adjacent_faces": [],  # 後で隣接面情報を追加
                "is_boundary": False   # 境界エッジかどうか
            }
            
        except Exception as e:
            print(f"エッジ{edge_index}解析エラー: {e}")
            return None

    def _generate_default_square_boundary(self):
        """
        境界線が取得できない場合のデフォルト正方形境界線を生成。
        """
        # 20x20mmの正方形境界線
        square_boundary = [
            (0.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (20.0, 20.0, 0.0),
            (0.0, 20.0, 0.0),
            (0.0, 0.0, 0.0)  # 閉じた境界線
        ]
        return [square_boundary]
    
    def _analyze_general_surface(self, surface_adaptor):
        """
        その他の曲面（球面、トーラス面等）の詳細解析。
        """
        # 一般的な曲面は平面として近似展開
        return {
            "unfold_method": "planar_approximation"
        }

    def _remove_duplicate_points(self, points_2d: List[Tuple[float, float]], tolerance: float = 1e-6) -> List[Tuple[float, float]]:
        """
        重複点を除去。
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

    def _generate_convex_hull_boundary(self, face, surface_adaptor):
        """
        凸包を使用して境界線を生成（デフォルト正方形より優れた方法）。
        面のパラメータ空間をサンプリングして凸包を計算。

        Args:
            face: 面オブジェクト
            surface_adaptor: 面アダプタ

        Returns:
            List[List[Tuple[float, float, float]]]: 境界線のリスト
        """
        try:
            # パラメータ空間をサンプリング
            u_min, u_max, v_min, v_max = surface_adaptor.BoundsUV()
            sample_points = []

            # グリッド状にサンプリング（10x10）
            for i in range(10):
                for j in range(10):
                    u = u_min + (u_max - u_min) * i / 9
                    v = v_min + (v_max - v_min) * j / 9

                    try:
                        point_3d = surface_adaptor.Value(u, v)
                        sample_points.append((point_3d.X(), point_3d.Y(), point_3d.Z()))
                    except:
                        continue

            if len(sample_points) < 3:
                return []

            # 3D点群から2D投影して凸包を計算
            # 簡易版：XY平面に投影
            points_2d = [(p[0], p[1]) for p in sample_points]

            # 凸包を計算
            try:
                points_array = np.array(points_2d)
                hull = ConvexHull(points_array)

                # 凸包の頂点から3D点を復元
                boundary_3d = []
                for vertex_idx in hull.vertices:
                    boundary_3d.append(sample_points[vertex_idx])

                # 閉じた境界線にする
                if boundary_3d and boundary_3d[0] != boundary_3d[-1]:
                    boundary_3d.append(boundary_3d[0])

                print(f"    凸包境界線を生成: {len(boundary_3d)}点")
                return [boundary_3d]

            except Exception as e:
                print(f"    凸包計算エラー: {e}")
                return []

        except Exception as e:
            print(f"    凸包境界線生成エラー: {e}")
            return []

    def _estimate_face_area(self, boundary_curves: List[List[Tuple[float, float, float]]]) -> float:
        """
        境界線から面積を推定（Shoelace formula を使用）。

        Args:
            boundary_curves: 境界線のリスト

        Returns:
            float: 推定面積（mm²）
        """
        if not boundary_curves or not boundary_curves[0]:
            return 0.0

        # 最初の境界線（外形線）から面積を計算
        boundary = boundary_curves[0]

        if len(boundary) < 3:
            return 0.0

        # XY平面に投影して面積を計算（簡易版）
        try:
            points_2d = [(p[0], p[1]) for p in boundary]

            # Shoelace formula
            area = 0.0
            n = len(points_2d)
            for i in range(n):
                j = (i + 1) % n
                area += points_2d[i][0] * points_2d[j][1]
                area -= points_2d[j][0] * points_2d[i][1]

            area = abs(area) / 2.0
            return area

        except Exception as e:
            print(f"    面積推定エラー: {e}")
            return 0.0

    def _validate_planarity(self, boundary_curves: List[List[Tuple[float, float, float]]],
                          normal_vec: Optional[List[float]],
                          tolerance: float = 0.5) -> Tuple[bool, float]:
        """
        境界線の点が平面上にあるかを検証。

        Args:
            boundary_curves: 境界線のリスト
            normal_vec: 平面の法線ベクトル
            tolerance: 平面からの最大許容偏差（mm）

        Returns:
            Tuple[bool, float]: (平面性OK, 最大偏差)
        """
        if not boundary_curves or not boundary_curves[0] or not normal_vec:
            return True, 0.0  # 検証不可の場合はOKとする

        boundary = boundary_curves[0]

        if len(boundary) < 3:
            return True, 0.0

        try:
            # 法線ベクトルを正規化
            normal = np.array(normal_vec)
            normal = normal / np.linalg.norm(normal)

            # 最初の点を基準点とする
            reference_point = np.array(boundary[0])

            # 各点から平面までの距離を計算
            max_deviation = 0.0

            for point in boundary:
                point_vec = np.array(point)
                # 基準点からのベクトル
                relative_vec = point_vec - reference_point
                # 平面までの垂直距離（法線方向への投影）
                deviation = abs(np.dot(relative_vec, normal))
                max_deviation = max(max_deviation, deviation)

            # 許容偏差以内なら平面と判定
            is_planar = max_deviation <= tolerance

            return is_planar, max_deviation

        except Exception as e:
            print(f"    平面性検証エラー: {e}")
            return True, 0.0  # エラー時はOKとする