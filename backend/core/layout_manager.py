"""
Layout Manager for BREP Papercraft Unfolding

This module handles the layout and positioning of unfolded groups on the output canvas.
It provides functionality for:
- Calculating bounding boxes for groups and overall layout
- Optimizing group placement to minimize paper usage
- Translating groups to their final positions
- Polygon-level overlap detection for accurate placement
"""

import copy
import math
from typing import List, Dict, Tuple, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from shapely.geometry import Polygon, box as shapely_box
    from shapely.ops import unary_union
    from shapely.prepared import prep as prepare_geometry
    from shapely import STRtree
    from shapely import affinity

    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    logger.info("Warning: Shapely not available. Using bounding box overlap detection only.")


class LayoutManager:
    """
    管理展開済みグループの配置とレイアウト最適化を行うクラス。
    重複回避・用紙サイズ最適化・効率的な配置アルゴリズムを提供。
    """

    def __init__(
        self,
        scale_factor: float = 10.0,
        page_format: str = "A4",
        page_orientation: str = "portrait",
    ):
        """
        Args:
            scale_factor: スケール倍率（デジタル-物理変換比率）
            page_format: ページフォーマット (A4, A3, Letter)
            page_orientation: ページ方向 ("portrait" or "landscape")
        """
        self.scale_factor = scale_factor
        self.page_format = page_format
        self.page_orientation = page_orientation

        # ページサイズ定義 (mm単位)
        self.page_sizes_mm = {
            "A4": {"width": 210, "height": 297},
            "A3": {"width": 297, "height": 420},
            "Letter": {"width": 216, "height": 279},
        }

        # 印刷マージン (mm)
        self.print_margin_mm = 10

        # 現在のページ寸法を計算
        self._calculate_page_dimensions()
        self._layout_orientation_cache: Dict[
            Tuple[int, bool], Tuple[Dict, List[Dict]]
        ] = {}
        self._polygon_fit_cache: Dict[int, bool] = {}
        self._shape_sensitive_cache: Dict[int, bool] = {}
        self._collision_geometry_cache: Dict[int, object] = {}
        self._buffered_collision_geometry_cache: Dict[Tuple[int, float], object] = {}
        self._fast_page_packing = False
        self.page_item_margin_mm = 3.0
        self.polygon_fit_occupancy_limit = 10

    def layout_unfolded_groups(self, unfolded_groups: List[Dict]) -> List[Dict]:
        """
        展開済みグループを紙面上に効率的に配置。
        重複回避・用紙サイズ最適化を実施。

        Args:
            unfolded_groups: 展開済みグループのリスト

        Returns:
            配置済みグループのリスト
        """
        if not unfolded_groups:
            return []

        # 各グループの境界ボックス計算
        for group in unfolded_groups:
            bbox = self.calculate_group_bbox(group)
            group["bbox"] = bbox

        # 面積の大きい順にソート
        unfolded_groups.sort(
            key=lambda g: g["bbox"]["width"] * g["bbox"]["height"], reverse=True
        )

        # A4印刷エリアに収まるよう配置
        page_size = self.page_sizes_mm[self.page_format]
        printable_width = page_size["width"] - 2 * self.print_margin_mm
        printable_height = (
            page_size["height"] - 2 * self.print_margin_mm - 25
        )  # タイトル分

        logger.info(f"印刷可能領域: {printable_width} x {printable_height} mm")

        # 重複回避配置アルゴリズム
        placed_groups = []
        occupied_areas = []  # 既に使用されている領域（bbox用）
        placed_polygon_groups = []  # 配置済みポリゴンデータ（ポリゴン重複検出用）
        margin_mm = 8  # 十分な間隔で線の重複を回避

        for group in unfolded_groups:
            bbox = group["bbox"]

            # 最適な配置位置を探索（bbox判定とポリゴン判定の両方を使用）
            position = self._find_non_overlapping_position_with_polygons(
                group, bbox, occupied_areas, placed_polygon_groups, margin_mm
            )

            # グループを配置
            offset_x = position["x"] - bbox["min_x"]
            offset_y = position["y"] - bbox["min_y"]

            positioned_group = self._translate_group(group, offset_x, offset_y)
            positioned_group["position"] = position

            placed_groups.append(positioned_group)
            placed_polygon_groups.append(positioned_group)  # ポリゴンデータも保存

            # 占有エリアを記録（マージン込み）
            occupied_area = {
                "min_x": position["x"] - margin_mm,
                "min_y": position["y"] - margin_mm,
                "max_x": position["x"] + bbox["width"] + margin_mm,
                "max_y": position["y"] + bbox["height"] + margin_mm,
            }
            occupied_areas.append(occupied_area)

            logger.info(
                f"グループ配置: ({position['x']:.1f}, {position['y']:.1f}) サイズ: {bbox['width']:.1f}x{bbox['height']:.1f}mm"
            )

        return placed_groups

    def _calculate_group_bbox(self, polygons: List[List[Tuple[float, float]]]) -> Dict:
        """
        グループ全体の境界ボックス計算

        Args:
            polygons: ポリゴンのリスト

        Returns:
            境界ボックス情報を含む辞書
        """
        if not polygons:
            return {
                "min_x": 0,
                "min_y": 0,
                "max_x": 0,
                "max_y": 0,
                "width": 0,
                "height": 0,
            }

        all_points = []
        for polygon in polygons:
            all_points.extend(polygon)

        if not all_points:
            return {
                "min_x": 0,
                "min_y": 0,
                "max_x": 0,
                "max_y": 0,
                "width": 0,
                "height": 0,
            }

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
            "height": max_y - min_y,
        }

    def calculate_group_bbox(self, group: Dict) -> Dict:
        """
        ポリゴンとタブを含むグループ全体の境界ボックスを計算する。
        """
        return self._calculate_group_bbox(
            list(group.get("polygons", [])) + list(group.get("tabs", []))
        )

    def _group_printable_area(self, group: Dict) -> float:
        area = 0.0
        for polygon in group.get("polygons", []):
            if len(polygon) < 3:
                continue
            area += abs(
                sum(
                    x1 * y2 - x2 * y1
                    for (x1, y1), (x2, y2) in zip(
                        polygon, polygon[1:] + polygon[:1]
                    )
                )
                / 2.0
            )
        return area

    def _translate_group(self, group: Dict, offset_x: float, offset_y: float) -> Dict:
        """
        グループ全体を指定オフセットで移動

        Args:
            group: 移動対象のグループ
            offset_x: X方向オフセット
            offset_y: Y方向オフセット

        Returns:
            移動後のグループ
        """
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
        translated_group["fold_lines"] = [
            [(x + offset_x, y + offset_y) for x, y in line]
            for line in group.get("fold_lines", [])
        ]
        translated_group["cut_lines"] = [
            [(x + offset_x, y + offset_y) for x, y in line]
            for line in group.get("cut_lines", [])
        ]
        translated_group["bbox"] = self.calculate_group_bbox(translated_group)

        return translated_group

    def _rotate_group(self, group: Dict, angle_degrees: float) -> Dict:
        """
        グループ全体を指定角度で回転する。紙面配置用の剛体変換なので形状寸法は変えない。
        """
        rotated_group = copy.deepcopy(group)
        theta = math.radians(angle_degrees)
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)

        def rotate_points(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
            return [
                (x * cos_theta - y * sin_theta, x * sin_theta + y * cos_theta)
                for x, y in points
            ]

        rotated_group["polygons"] = [
            rotate_points(polygon) for polygon in group.get("polygons", [])
        ]
        rotated_group["tabs"] = [rotate_points(tab) for tab in group.get("tabs", [])]
        rotated_group["fold_lines"] = [
            rotate_points(line) for line in group.get("fold_lines", [])
        ]
        rotated_group["cut_lines"] = [
            rotate_points(line) for line in group.get("cut_lines", [])
        ]
        rotated_group["bbox"] = self.calculate_group_bbox(rotated_group)
        rotated_group["layout_rotation"] = angle_degrees
        rotated_group.pop("_merged_geometry", None)
        return rotated_group

    def _layout_orientations(
        self, group: Dict, orthogonal_only: bool = False
    ) -> List[Dict]:
        """
        配置候補として複数の回転角を返す。
        """
        cache_key = (id(group), orthogonal_only)
        cached = self._layout_orientation_cache.get(cache_key)
        if cached is not None and cached[0] is group:
            return cached[1]

        orientations = []
        seen_orientations = set()
        shape_sensitive = self._is_shape_sensitive_for_rotation(group)
        if orthogonal_only:
            angles = (0, 90, 180, 270) if shape_sensitive else (0, 90)
        else:
            angles = range(0, 360, 15) if shape_sensitive else range(0, 180, 15)
        for angle in angles:
            rotated_group = self._rotate_group(group, float(angle))
            bbox = rotated_group["bbox"]
            key = (round(bbox["width"], 3), round(bbox["height"], 3))
            if shape_sensitive:
                key = key + (self._normalized_layout_shape_key(rotated_group),)
            if key in seen_orientations:
                continue
            seen_orientations.add(key)
            orientations.append(rotated_group)

        self._layout_orientation_cache[cache_key] = (group, orientations)
        return orientations

    def _packing_orientations(self, group: Dict) -> List[Dict]:
        variants = self._layout_orientations(group)
        max_fast_orientations = 4
        if not self._fast_page_packing or len(variants) <= max_fast_orientations:
            return variants

        orthogonal = [
            variant
            for variant in variants
            if abs(variant.get("layout_rotation", 0) % 90) < 1e-6
        ]
        oblique = [
            variant
            for variant in variants
            if abs(variant.get("layout_rotation", 0) % 90) >= 1e-6
        ]
        oblique.sort(
            key=lambda variant: (
                variant["bbox"]["width"] * variant["bbox"]["height"],
                max(
                    variant["bbox"]["width"] / max(self.printable_width_mm, 1e-9),
                    variant["bbox"]["height"] / max(self.printable_height_mm, 1e-9),
                ),
            )
        )
        return orthogonal + oblique[
            : max(0, max_fast_orientations - len(orthogonal))
        ]

    def _is_shape_sensitive_for_rotation(self, group: Dict) -> bool:
        cache_key = id(group)
        cached = self._shape_sensitive_cache.get(cache_key)
        if cached is not None:
            return cached

        result = len(group.get("polygons", [])) + len(group.get("tabs", [])) > 1
        if not result and SHAPELY_AVAILABLE:
            geometry = self._merge_group_polygons(
                self._group_collision_polygons(group)
            )
            if geometry is not None and not geometry.is_empty:
                hull_area = geometry.convex_hull.area
                result = hull_area > 1e-9 and geometry.area / hull_area < 0.98

        self._shape_sensitive_cache[cache_key] = result
        return result

    def _normalized_layout_shape_key(self, group: Dict) -> Tuple:
        bbox = group["bbox"]
        min_x = bbox["min_x"]
        min_y = bbox["min_y"]
        polygons = []
        for polygon in self._group_collision_polygons(group):
            polygons.append(
                tuple((round(x - min_x, 3), round(y - min_y, 3)) for x, y in polygon)
            )
        return tuple(polygons)

    def _reset_layout_caches(self) -> None:
        self._layout_orientation_cache.clear()
        self._polygon_fit_cache.clear()
        self._shape_sensitive_cache.clear()
        self._collision_geometry_cache.clear()
        self._buffered_collision_geometry_cache.clear()

    def required_scale_to_fit_group(
        self, group: Dict, max_width: float, max_height: float
    ) -> float:
        """
        グループ単体が指定矩形に入るために必要な最小縮尺分母を返す。
        回転候補のうち最も大きく置ける向きを採用する。
        """
        best_scale = None
        for variant in self._layout_orientations(group):
            bbox = variant["bbox"]
            width = bbox["width"]
            height = bbox["height"]
            if width <= 0 and height <= 0:
                continue
            candidate = max(
                width / max_width if max_width > 0 else 1.0,
                height / max_height if max_height > 0 else 1.0,
            )
            best_scale = candidate if best_scale is None else min(best_scale, candidate)

        if best_scale is None:
            return 1.0

        return max(1e-6, best_scale)

    def _oriented_bbox_for_sort(self, group: Dict) -> Dict:
        """
        ページ配置で実際に使いやすい向きのbboxを返す。
        回転前bboxだけでソートすると、斜めの細長い部品が過大評価され、
        最大部品より前のページに小部品だけが出るため、回転候補を考慮する。
        """
        variants = self._packing_orientations(group)
        if not variants:
            return group.get("bbox") or self.calculate_group_bbox(group)

        fitting_variants = [
            variant
            for variant in variants
            if variant["bbox"]["width"] <= self.printable_width_mm
            and variant["bbox"]["height"] <= self.printable_height_mm
        ]
        candidates = fitting_variants or variants

        def score(variant: Dict) -> Tuple[float, float]:
            bbox = variant["bbox"]
            area = bbox["width"] * bbox["height"]
            fit_ratio = max(
                bbox["width"] / self.printable_width_mm
                if self.printable_width_mm > 0
                else 1.0,
                bbox["height"] / self.printable_height_mm
                if self.printable_height_mm > 0
                else 1.0,
            )
            return area, fit_ratio

        return min(candidates, key=score)["bbox"]

    def _layout_sort_key(self, group: Dict) -> Tuple[float, float]:
        bbox = self._oriented_bbox_for_sort(group)
        return bbox["width"] * bbox["height"], max(bbox["width"], bbox["height"])

    def _create_shapely_polygon(
        self, polygon_points: List[Tuple[float, float]]
    ) -> Optional["Polygon"]:
        """
        Shapelyポリゴンオブジェクトを作成

        Args:
            polygon_points: ポリゴンの頂点リスト

        Returns:
            Shapelyポリゴンオブジェクト、または作成できない場合None
        """
        if not SHAPELY_AVAILABLE or len(polygon_points) < 3:
            return None

        try:
            # 閉じたポリゴンにする（最初と最後の点が異なる場合）
            if polygon_points[0] != polygon_points[-1]:
                polygon_points = polygon_points + [polygon_points[0]]
            return Polygon(polygon_points)
        except Exception as e:
            logger.info(f"ポリゴン作成エラー: {e}")
            return None

    def _merge_group_polygons(
        self,
        polygons: List[List[Tuple[float, float]]],
        offset: Tuple[float, float] = (0, 0),
    ) -> Optional["Polygon"]:
        """
        グループ内の全ポリゴンをunary_unionで結合して単一ジオメトリにする。
        事前にオフセットを適用してから結合する。

        Args:
            polygons: ポリゴンの頂点リストのリスト
            offset: 各ポリゴンに適用するオフセット (dx, dy)

        Returns:
            結合されたShapelyジオメトリ、または作成できない場合None
        """
        if not SHAPELY_AVAILABLE:
            return None

        shapely_polys = []
        dx, dy = offset
        for poly_points in polygons:
            if dx != 0 or dy != 0:
                moved = [(x + dx, y + dy) for x, y in poly_points]
            else:
                moved = poly_points
            shapely_poly = self._create_shapely_polygon(moved)
            if shapely_poly is not None and shapely_poly.is_valid:
                shapely_polys.append(shapely_poly)
            elif shapely_poly is not None:
                # 無効なポリゴンを修復
                fixed = shapely_poly.buffer(0)
                if not fixed.is_empty:
                    shapely_polys.append(fixed)

        if not shapely_polys:
            return None

        if len(shapely_polys) == 1:
            return shapely_polys[0]

        return unary_union(shapely_polys)

    def _polygons_overlap(
        self,
        polygons1: List[List[Tuple[float, float]]],
        polygons2: List[List[Tuple[float, float]]],
        offset1: Tuple[float, float] = (0, 0),
        offset2: Tuple[float, float] = (0, 0),
    ) -> bool:
        """
        2つのポリゴングループが重複するかをチェック

        Args:
            polygons1: 最初のポリゴングループ
            polygons2: 2番目のポリゴングループ
            offset1: 最初のグループのオフセット
            offset2: 2番目のグループのオフセット

        Returns:
            重複する場合True
        """
        if not SHAPELY_AVAILABLE:
            return False  # Shapelyが利用できない場合はbbox判定に依存

        # 各グループのポリゴンを移動してShapelyオブジェクトに変換
        shapely_polys1 = []
        for poly in polygons1:
            moved_poly = [(x + offset1[0], y + offset1[1]) for x, y in poly]
            shapely_poly = self._create_shapely_polygon(moved_poly)
            if shapely_poly:
                shapely_polys1.append(shapely_poly)

        shapely_polys2 = []
        for poly in polygons2:
            moved_poly = [(x + offset2[0], y + offset2[1]) for x, y in poly]
            shapely_poly = self._create_shapely_polygon(moved_poly)
            if shapely_poly:
                shapely_polys2.append(shapely_poly)

        # 各ポリゴンペアで交差チェック
        for poly1 in shapely_polys1:
            for poly2 in shapely_polys2:
                if poly1.intersects(poly2):
                    # 接触のみか重なりかを確認
                    intersection = poly1.intersection(poly2)
                    # 面積のある交差（重なり）か、完全包含をチェック
                    if (
                        intersection.area > 1e-6
                        or poly1.contains(poly2)
                        or poly2.contains(poly1)
                    ):
                        return True

        return False

    def _find_non_overlapping_position_with_polygons(
        self,
        group: Dict,
        bbox: Dict,
        occupied_areas: List[Dict],
        placed_polygon_groups: List[Dict],
        margin_mm: float,
    ) -> Dict:
        """
        他のグループと重複しない配置位置を探索（ポリゴンレベルの判定付き）。
        STRtreeを使用して空間索引による高速な重複判定を実行。

        Args:
            group: 配置するグループ（ポリゴンデータ含む）
            bbox: 配置するグループの境界ボックス
            occupied_areas: 既に占有されている領域のリスト（bbox用）
            placed_polygon_groups: 配置済みのポリゴングループ
            margin_mm: 必要なマージン

        Returns:
            配置位置 {"x": float, "y": float}
        """
        # グリッドベースで位置を探索
        grid_step = 5  # 5mm刻みで探索
        max_x = 300  # 最大探索範囲
        max_y = 400

        # --- STRtree高速化: 事前に配置済みのジオメトリを構築 ---
        # 配置済みbboxからSTRtreeを構築（bbox判定高速化）
        bbox_tree = None
        bbox_geoms = []
        if SHAPELY_AVAILABLE and occupied_areas:
            for area in occupied_areas:
                bbox_geoms.append(
                    shapely_box(
                        area["min_x"],
                        area["min_y"],
                        area["max_x"],
                        area["max_y"],
                    )
                )
            bbox_tree = STRtree(bbox_geoms)

        # 配置済みポリゴンのunary_unionをキャッシュ（ポリゴン判定高速化）
        placed_merged = None
        placed_poly_list = []
        if SHAPELY_AVAILABLE and placed_polygon_groups:
            for placed_group in placed_polygon_groups:
                merged = placed_group.get("_merged_geometry")
                if merged is None:
                    merged = self._merge_group_polygons(placed_group["polygons"])
                    placed_group["_merged_geometry"] = merged
                if merged is not None and not merged.is_empty:
                    placed_poly_list.append(merged)
            if placed_poly_list:
                placed_merged = unary_union(placed_poly_list)

        # 候補グループのポリゴンを事前にunary_union化（1回だけ）
        candidate_base_geom = None
        if SHAPELY_AVAILABLE:
            candidate_base_geom = self._merge_group_polygons(
                group["polygons"],
                offset=(-bbox["min_x"], -bbox["min_y"]),
            )

        for y in range(0, max_y, grid_step):
            for x in range(0, max_x, grid_step):
                candidate_box = (
                    shapely_box(x, y, x + bbox["width"], y + bbox["height"])
                    if SHAPELY_AVAILABLE
                    else None
                )

                # まずbboxレベルで重複チェック（STRtreeで高速）
                if bbox_tree is not None and candidate_box is not None:
                    # STRtreeクエリ: candidate_boxと交差する可能性のあるbboxを検索
                    nearby_indices = bbox_tree.query(candidate_box)
                    bbox_overlaps = False
                    for idx in nearby_indices:
                        if candidate_box.intersects(bbox_geoms[idx]):
                            bbox_overlaps = True
                            break
                    if bbox_overlaps:
                        continue
                elif occupied_areas:
                    # Shapelyなしのフォールバック
                    candidate_area = {
                        "min_x": x,
                        "min_y": y,
                        "max_x": x + bbox["width"],
                        "max_y": y + bbox["height"],
                    }
                    if self._areas_overlap(candidate_area, occupied_areas):
                        continue

                # bboxが重複しない場合、ポリゴンレベルでチェック（精密）
                overlap_found = False
                if candidate_base_geom is not None and placed_merged is not None:
                    # affinity.translateで候補ポリゴンをグリッド位置に移動
                    translated_candidate = affinity.translate(
                        candidate_base_geom, xoff=x, yoff=y
                    )
                    if translated_candidate.intersects(placed_merged):
                        intersection = translated_candidate.intersection(placed_merged)
                        if intersection.area > 1e-6:
                            overlap_found = True

                if not overlap_found:
                    return {"x": x, "y": y}

        # 重複しない位置が見つからない場合は右端に配置
        rightmost_x = max([area["max_x"] for area in occupied_areas], default=0)
        return {"x": rightmost_x + margin_mm, "y": 0}

    def _find_non_overlapping_position(
        self, bbox: Dict, occupied_areas: List[Dict], margin_mm: float
    ) -> Dict:
        """
        他のグループと重複しない配置位置を探索。

        Args:
            bbox: 配置するグループの境界ボックス
            occupied_areas: 既に占有されている領域のリスト
            margin_mm: 必要なマージン

        Returns:
            配置位置 {"x": float, "y": float}
        """
        # グリッドベースで位置を探索
        grid_step = 5  # 5mm刻みで探索
        max_x = 300  # 最大探索範囲
        max_y = 400

        for y in range(0, max_y, grid_step):
            for x in range(0, max_x, grid_step):
                candidate_area = {
                    "min_x": x,
                    "min_y": y,
                    "max_x": x + bbox["width"],
                    "max_y": y + bbox["height"],
                }

                # 既存エリアとの重複チェック
                if not self._areas_overlap(candidate_area, occupied_areas):
                    return {"x": x, "y": y}

        # 重複しない位置が見つからない場合は右端に配置
        rightmost_x = max([area["max_x"] for area in occupied_areas], default=0)
        return {"x": rightmost_x + margin_mm, "y": 0}

    def _areas_overlap(self, candidate: Dict, occupied_areas: List[Dict]) -> bool:
        """
        候補エリアが既存の占有エリアと重複するかチェック。

        Args:
            candidate: 候補エリア
            occupied_areas: 既存の占有エリアリスト

        Returns:
            重複する場合True
        """
        for occupied in occupied_areas:
            # 矩形の重複判定
            if not (
                candidate["max_x"] <= occupied["min_x"]
                or candidate["min_x"] >= occupied["max_x"]
                or candidate["max_y"] <= occupied["min_y"]
                or candidate["min_y"] >= occupied["max_y"]
            ):
                return True
        return False

    def calculate_overall_bbox(self, placed_groups: List[Dict]) -> Dict:
        """
        配置済み全グループの境界ボックス計算

        Args:
            placed_groups: 配置済みグループのリスト

        Returns:
            全体の境界ボックス情報を含む辞書
        """
        if not placed_groups:
            return {
                "min_x": 0,
                "min_y": 0,
                "max_x": 0,
                "max_y": 0,
                "width": 0,
                "height": 0,
            }

        all_points = []
        for group in placed_groups:
            for polygon in group["polygons"]:
                all_points.extend(polygon)
            for tab in group.get("tabs", []):
                all_points.extend(tab)

        if not all_points:
            return {
                "min_x": 0,
                "min_y": 0,
                "max_x": 0,
                "max_y": 0,
                "width": 0,
                "height": 0,
            }

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
            "height": max_y - min_y,
        }

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

        # 印刷可能エリア計算
        self.printable_width_mm = self.page_width_mm - 2 * self.print_margin_mm
        self.printable_height_mm = self.page_height_mm - 2 * self.print_margin_mm

    def _format_scale_as_fraction(self, scale: float) -> str:
        """
        スケール比率を分数形式の文字列に変換（ユーザーフレンドリーな表示用）

        例:
            0.5 → "1/2"
            0.333 → "約1/3"
            0.25 → "1/4"
            0.2 → "1/5"
            0.633 → "約2/3"
            0.75 → "3/4"

        Args:
            scale: スケール比率（0.0-1.0）

        Returns:
            分数形式の文字列
        """
        from fractions import Fraction

        # 一般的な分数との近似を判定
        common_fractions = {
            1.0: "1/1",
            0.75: "3/4",
            0.667: "2/3",
            0.5: "1/2",
            0.333: "1/3",
            0.25: "1/4",
            0.2: "1/5",
            0.167: "1/6",
            0.125: "1/8",
            0.1: "1/10",
        }

        # 最も近い一般的な分数を探す
        tolerance = 0.05  # 5%の誤差を許容
        for common_scale, fraction_text in common_fractions.items():
            if abs(scale - common_scale) < tolerance:
                if abs(scale - common_scale) < 0.01:
                    return fraction_text
                else:
                    return f"約{fraction_text}"

        # 一般的な分数にマッチしない場合、Fractionで近似値を計算
        # 分母を20以下に制限して読みやすい分数にする
        fraction = Fraction(scale).limit_denominator(20)

        if fraction.numerator == 1:
            return f"約1/{fraction.denominator}"
        else:
            return f"約{fraction.numerator}/{fraction.denominator}"

    def layout_for_pages(
        self, unfolded_groups: List[Dict]
    ) -> Tuple[List[List[Dict]], List[Dict]]:
        """
        展開済みグループをページ単位で配置。
        各ページが印刷可能サイズに収まるようにbinpacking。

        Args:
            unfolded_groups: 展開済みグループのリスト

        Returns:
            Tuple[ページごとに配置されたグループのリスト, 警告情報のリスト]
        """
        if not unfolded_groups:
            return [], []

        self._reset_layout_caches()

        # 警告情報を収集するリスト
        warnings = []
        printable_groups = []
        skipped_face_numbers = []
        skipped_group_count = 0

        # 各グループの境界ボックス計算。
        # 縮尺はStepUnfoldGeneratorで紙上寸法へ変換済みのため、ここでは勝手に縮小しない。
        for group in unfolded_groups:
            bbox = self.calculate_group_bbox(group)
            group["bbox"] = bbox
            if self._group_printable_area(group) <= 1e-6:
                skipped_group_count += 1
                skipped_face_numbers.extend(group.get("face_numbers", []))
                continue

            printable_groups.append(group)

            orientations = self._layout_orientations(group)
            fits_any_orientation = any(
                variant["bbox"]["width"] <= self.printable_width_mm
                and variant["bbox"]["height"] <= self.printable_height_mm
                for variant in orientations
            )
            if not fits_any_orientation:
                logger.info(
                    f"警告: グループサイズ({bbox['width']:.1f}x{bbox['height']:.1f}mm)が"
                    f"印刷可能エリア({self.printable_width_mm}x{self.printable_height_mm}mm)を超えています"
                )
                warnings.append(
                    {
                        "type": "page_overflow",
                        "message": (
                            "一部の展開パーツが選択した用紙の印刷可能領域を超えています。"
                            "縮尺を小さくするか、用紙最大（自動）を選択してください。"
                        ),
                        "details": {
                            "size_mm": {
                                "width": round(bbox["width"], 1),
                                "height": round(bbox["height"], 1),
                            },
                            "overflow": {
                                "width": all(
                                    variant["bbox"]["width"] > self.printable_width_mm
                                    for variant in orientations
                                ),
                                "height": all(
                                    variant["bbox"]["height"] > self.printable_height_mm
                                    for variant in orientations
                                ),
                            },
                            "page_format": self.page_format,
                            "page_orientation": self.page_orientation,
                            "printable_area_mm": {
                                "width": self.printable_width_mm,
                                "height": self.printable_height_mm,
                            },
                        },
                    }
                )

        if skipped_face_numbers:
            warnings.append(
                {
                    "type": "degenerate_groups_skipped",
                    "message": "面積を持たない退化面を展開図から除外しました。",
                    "details": {
                        "group_count": skipped_group_count,
                        "face_numbers": skipped_face_numbers,
                    },
                }
            )

        if not printable_groups:
            return [], warnings

        margin_mm = self.page_item_margin_mm
        paged_groups = self._pack_groups_with_strategies(
            printable_groups, margin_mm, allow_overflow=True
        )

        logger.info(f"ページレイアウト完了: {len(paged_groups)}ページに分割")
        return paged_groups, warnings

    def can_pack_groups_on_single_page(
        self, unfolded_groups: List[Dict], margin_mm: float = 5
    ) -> bool:
        """
        与えられた紙上寸法のグループ群が、選択用紙1枚に配置できるかを判定する。
        実際の配置と同じ向き候補・候補点探索を使う。
        """
        groups = copy.deepcopy(unfolded_groups)
        self._reset_layout_caches()
        for group in groups:
            group["bbox"] = self.calculate_group_bbox(group)

        paged_groups = self._pack_groups_with_strategies(
            groups, margin_mm, allow_overflow=False
        )
        if paged_groups is None:
            return False

        return len(paged_groups) == 1

    def _pack_groups_with_strategies(
        self, groups: List[Dict], margin: float, allow_overflow: bool
    ) -> Optional[List[List[Dict]]]:
        previous_fast_packing = self._fast_page_packing
        self._fast_page_packing = len(groups) > 40
        try:
            best_pages = None
            best_score = None

            for ordered_groups in self._packing_orderings(groups):
                if self._fast_page_packing:
                    candidates = [
                        self._pack_groups_across_pages(
                            ordered_groups, margin, allow_overflow=allow_overflow
                        )
                    ]
                    primary_pages = candidates[0]
                    if (
                        primary_pages
                        and len(primary_pages) > 1
                        and self._page_shape_utilization(primary_pages[-1]) < 0.05
                    ):
                        candidates.append(
                            self._pack_groups_in_order(
                                ordered_groups,
                                margin,
                                allow_overflow=allow_overflow,
                            )
                        )
                else:
                    candidates = [
                        self._pack_groups_in_order(
                            ordered_groups, margin, allow_overflow=allow_overflow
                        )
                    ]

                for pages in candidates:
                    if pages is None:
                        continue

                    score = self._paged_layout_score(pages)
                    if best_score is None or score < best_score:
                        best_pages = pages
                        best_score = score

            return best_pages
        finally:
            self._fast_page_packing = previous_fast_packing

    def _page_shape_utilization(self, page: List[Dict]) -> float:
        shape_area = sum(self._group_printable_area(group) for group in page)
        page_area = self.printable_width_mm * self.printable_height_mm
        return shape_area / max(page_area, 1e-9)

    def _packing_orderings(self, groups: List[Dict]) -> List[List[Dict]]:
        indexed_groups = list(enumerate(groups))

        def oriented_bbox(group: Dict) -> Dict:
            return self._oriented_bbox_for_sort(group)

        def raw_bbox(group: Dict) -> Dict:
            return group.get("bbox") or self.calculate_group_bbox(group)

        def aspect_distance(group: Dict) -> float:
            bbox = oriented_bbox(group)
            width = max(bbox["width"], 1e-9)
            height = max(bbox["height"], 1e-9)
            page_ratio = self.printable_width_mm / max(self.printable_height_mm, 1e-9)
            return abs(math.log((width / height) / page_ratio))

        strategies = [
            lambda item: (
                self._layout_sort_key(item[1])[0],
                self._layout_sort_key(item[1])[1],
            ),
            lambda item: (
                oriented_bbox(item[1])["height"],
                oriented_bbox(item[1])["width"],
            ),
            lambda item: (
                oriented_bbox(item[1])["width"],
                oriented_bbox(item[1])["height"],
            ),
            lambda item: (
                max(oriented_bbox(item[1])["width"], oriented_bbox(item[1])["height"]),
                min(oriented_bbox(item[1])["width"], oriented_bbox(item[1])["height"]),
            ),
            lambda item: (
                min(oriented_bbox(item[1])["width"], oriented_bbox(item[1])["height"]),
                max(oriented_bbox(item[1])["width"], oriented_bbox(item[1])["height"]),
            ),
            lambda item: (
                raw_bbox(item[1])["width"] * raw_bbox(item[1])["height"],
                max(raw_bbox(item[1])["width"], raw_bbox(item[1])["height"]),
            ),
            lambda item: (-aspect_distance(item[1]), self._layout_sort_key(item[1])[0]),
            lambda item: (aspect_distance(item[1]), self._layout_sort_key(item[1])[0]),
        ]

        # PLATEAUモデルなど大量のグループがある場合、配置処理が極端に遅くなるのを防ぐため、
        # グループ数に応じて評価する戦略（並び順）の数を制限する
        if len(groups) > 40:
            strategies = strategies[:1]
        elif len(groups) > 20:
            strategies = strategies[:2]

        orderings = []
        seen_orders = set()
        for strategy in strategies:
            ordered = sorted(indexed_groups, key=strategy, reverse=True)
            order_key = tuple(index for index, _ in ordered)
            if order_key in seen_orders:
                continue
            seen_orders.add(order_key)
            orderings.append([group for _, group in ordered])

        original_key = tuple(index for index, _ in indexed_groups)
        if len(groups) <= 40 and original_key not in seen_orders:
            orderings.append([group for _, group in indexed_groups])

        return orderings

    def _pack_groups_across_pages(
        self, ordered_groups: List[Dict], margin: float, allow_overflow: bool
    ) -> Optional[List[List[Dict]]]:
        page_states = []

        for group in ordered_groups:
            best_page = None
            best_placement = None
            best_score = None

            for page_index, state in enumerate(page_states):
                placement = self._find_oriented_position_in_page(
                    group,
                    state["occupied_areas"],
                    state["groups"],
                    state["free_areas"],
                    self.printable_width_mm,
                    self.printable_height_mm,
                    margin,
                )
                if placement is None:
                    continue

                score = (placement["score"], page_index)
                if best_score is None or score < best_score:
                    best_page = state
                    best_placement = placement
                    best_score = score

            if best_page is None:
                placement = self._find_oriented_position_in_page(
                    group,
                    [],
                    [],
                    [
                        {
                            "min_x": 0.0,
                            "min_y": 0.0,
                            "max_x": self.printable_width_mm,
                            "max_y": self.printable_height_mm,
                        }
                    ],
                    self.printable_width_mm,
                    self.printable_height_mm,
                    margin,
                )
                if placement is None:
                    if not allow_overflow:
                        return None
                    placement = self._first_page_position(group)

                best_page = {
                    "groups": [],
                    "occupied_areas": [],
                    "free_areas": [
                        {
                            "min_x": 0.0,
                            "min_y": 0.0,
                            "max_x": self.printable_width_mm,
                            "max_y": self.printable_height_mm,
                        }
                    ],
                }
                page_states.append(best_page)
                best_placement = placement

            positioned_group, occupied_area = self._place_group_on_page(
                best_placement, margin
            )
            best_page["groups"].append(positioned_group)
            best_page["occupied_areas"].append(occupied_area)
            best_page["free_areas"] = self._split_free_areas(
                best_page["free_areas"], occupied_area
            )

        return [state["groups"] for state in page_states]

    def _pack_groups_in_order(
        self, ordered_groups: List[Dict], margin: float, allow_overflow: bool
    ) -> Optional[List[List[Dict]]]:
        paged_groups = []
        unplaced_groups = list(ordered_groups)

        while unplaced_groups:
            current_page = []
            page_occupied_areas = []
            page_polygon_groups = []
            page_free_areas = [
                {
                    "min_x": 0.0,
                    "min_y": 0.0,
                    "max_x": self.printable_width_mm,
                    "max_y": self.printable_height_mm,
                }
            ]

            while unplaced_groups:
                next_index, placement = self._find_next_fitting_group_for_page(
                    unplaced_groups,
                    page_occupied_areas,
                    page_polygon_groups,
                    page_free_areas,
                    self.printable_width_mm,
                    self.printable_height_mm,
                    margin,
                )

                if next_index is None or placement is None:
                    if current_page:
                        break

                    if not allow_overflow:
                        return None

                    placement = self._first_page_position(unplaced_groups[0])
                    next_index = 0

                unplaced_groups.pop(next_index)
                positioned_group, occupied_area = self._place_group_on_page(
                    placement, margin
                )
                current_page.append(positioned_group)
                page_occupied_areas.append(occupied_area)
                page_polygon_groups.append(positioned_group)
                page_free_areas = self._split_free_areas(page_free_areas, occupied_area)

            paged_groups.append(current_page)

        return paged_groups

    def _paged_layout_score(self, paged_groups: List[List[Dict]]) -> Tuple:
        page_scores = []
        for page in paged_groups:
            bbox = self.calculate_overall_bbox(page)
            used_width = min(self.printable_width_mm, bbox["width"])
            used_height = min(self.printable_height_mm, bbox["height"])
            used_area = used_width * used_height
            actual_area = sum(
                group["bbox"]["width"] * group["bbox"]["height"] for group in page
            )
            utilization = actual_area / max(
                self.printable_width_mm * self.printable_height_mm, 1e-9
            )
            page_scores.append((used_area, used_height, used_width, -utilization))

        total_used_area = sum(score[0] for score in page_scores)
        total_used_height = sum(score[1] for score in page_scores)
        worst_utilization = max(score[3] for score in page_scores) if page_scores else 0
        return (
            len(paged_groups),
            total_used_area,
            total_used_height,
            worst_utilization,
            tuple(page_scores),
        )

    def _find_next_fitting_group_for_page(
        self,
        groups: List[Dict],
        occupied_areas: List[Dict],
        placed_polygon_groups: List[Dict],
        free_areas: List[Dict],
        max_width: float,
        max_height: float,
        margin: float,
    ) -> Tuple[Optional[int], Optional[Dict]]:
        """
        現在ページに入る次のグループを探す。
        グループは事前に大きい順へ並んでいるため、入らない候補だけを飛ばして
        余白に入る最大寄りの候補を採用する。
        """
        if not occupied_areas:
            for index, group in enumerate(groups):
                placement = self._find_oriented_position_in_page(
                    group,
                    occupied_areas,
                    placed_polygon_groups,
                    free_areas,
                    max_width,
                    max_height,
                    margin,
                )
                if placement is not None:
                    return index, placement

            return None, None

        current_max_x = max(area["max_x"] for area in occupied_areas)
        current_max_y = max(area["max_y"] for area in occupied_areas)
        best_candidate = None
        for index, group in enumerate(groups):
            placement = self._find_oriented_position_in_page(
                group,
                occupied_areas,
                placed_polygon_groups,
                free_areas,
                max_width,
                max_height,
                margin,
            )
            if placement is None:
                continue

            bbox = placement["group"]["bbox"]
            position = placement["position"]
            reserved = self._reserved_area_for_bbox(
                bbox, position, max_width, max_height, margin
            )
            result_max_x = max(current_max_x, reserved["max_x"])
            result_max_y = max(current_max_y, reserved["max_y"])
            area = bbox["width"] * bbox["height"]
            score = (
                placement["score"],
                result_max_y,
                result_max_x,
                position["y"],
                position["x"],
                -area,
                index,
            )
            candidate = (score, index, placement)
            if best_candidate is None or candidate[0] < best_candidate[0]:
                best_candidate = candidate

            if len(groups) > 30:
                return candidate[1], candidate[2]

        if best_candidate is not None:
            return best_candidate[1], best_candidate[2]

        return None, None

    def _place_group_on_page(
        self, placement: Dict, margin: float
    ) -> Tuple[Dict, Dict]:
        variant = placement["group"]
        bbox = variant["bbox"]
        position = placement["position"]

        offset_x = position["x"] - bbox["min_x"]
        offset_y = position["y"] - bbox["min_y"]

        positioned_group = self._translate_group(variant, offset_x, offset_y)
        positioned_group["position"] = position
        positioned_group["layout_rotation"] = variant.get("layout_rotation", 0)

        occupied_area = placement.get(
            "reserved_area",
            {
                "min_x": position["x"],
                "min_y": position["y"],
                "max_x": position["x"] + bbox["width"] + margin,
                "max_y": position["y"] + bbox["height"] + margin,
            },
        )
        return positioned_group, occupied_area

    def _first_page_position(self, group: Dict) -> Dict:
        orientations = self._packing_orientations(group)
        fitting_orientations = [
            variant
            for variant in orientations
            if variant["bbox"]["width"] <= self.printable_width_mm
            and variant["bbox"]["height"] <= self.printable_height_mm
        ]
        selected = fitting_orientations[0] if fitting_orientations else orientations[0]
        return {"group": selected, "position": {"x": 0, "y": 0}}

    def _find_oriented_position_in_page(
        self,
        group: Dict,
        occupied_areas: List[Dict],
        placed_polygon_groups: List[Dict],
        free_areas: List[Dict],
        max_width: float,
        max_height: float,
        margin: float,
        allow_polygon_fit: bool = True,
    ) -> Optional[Dict]:
        placements = []
        variants = self._packing_orientations(group)

        for variant in variants:
            bbox = variant["bbox"]
            for free_area in self._sorted_free_areas(free_areas):
                for position in self._candidate_positions_in_free_area(bbox, free_area):
                    if not self._position_fits_in_page(
                        bbox,
                        position,
                        free_area,
                        occupied_areas,
                        max_width,
                        max_height,
                        margin,
                    ):
                        continue
                    free_width = free_area["max_x"] - free_area["min_x"]
                    free_height = free_area["max_y"] - free_area["min_y"]
                    leftover_width = free_width - bbox["width"]
                    leftover_height = free_height - bbox["height"]
                    reserved = self._reserved_area_for_bbox(
                        bbox, position, max_width, max_height, margin
                    )
                    if occupied_areas:
                        rotation = variant.get("layout_rotation", 0)
                        oblique_penalty = 0 if abs(rotation % 90) < 1e-6 else 1
                        score = (
                            oblique_penalty,
                            min(leftover_width, leftover_height),
                            max(leftover_width, leftover_height),
                            reserved["max_y"],
                            reserved["max_x"],
                            position["y"],
                            position["x"],
                        )
                    else:
                        rotation = variant.get("layout_rotation", 0)
                        oblique_penalty = 0 if abs(rotation % 90) < 1e-6 else 1
                        page_ratio = max_width / max(max_height, 1e-9)
                        item_ratio = bbox["width"] / max(bbox["height"], 1e-9)
                        score = (
                            oblique_penalty,
                            abs(math.log(item_ratio / page_ratio)),
                            reserved["max_y"],
                            reserved["max_x"],
                            min(leftover_width, leftover_height),
                            max(leftover_width, leftover_height),
                            position["y"],
                            position["x"],
                        )
                    placements.append(
                        {
                            "group": variant,
                            "position": position,
                            "reserved_area": reserved,
                            "score": score,
                        }
                    )

        if placements:
            placements.sort(key=lambda item: item["score"])
            return {
                "group": placements[0]["group"],
                "position": placements[0]["position"],
                "reserved_area": placements[0]["reserved_area"],
                "score": placements[0]["score"],
            }

        if (
            not allow_polygon_fit
            or not occupied_areas
            or len(occupied_areas) >= self.polygon_fit_occupancy_limit
        ):
            return None

        polygon_variants = [
            variant
            for variant in variants
            if self._should_use_polygon_fit(variant, variant["bbox"])
        ]
        if not polygon_variants:
            return None

        placed_geometry = self._placed_page_geometry(placed_polygon_groups, margin)
        if placed_geometry is None:
            return None
        prepared_geometry = prepare_geometry(placed_geometry)

        for variant in polygon_variants:
            bbox = variant["bbox"]
            for position in self._polygon_candidate_positions(
                bbox, occupied_areas, max_width, max_height
            ):
                if not self._polygon_position_fits_in_page(
                    variant,
                    bbox,
                    position,
                    placed_geometry,
                    max_width,
                    max_height,
                    margin,
                    prepared_geometry=prepared_geometry,
                ):
                    continue
                reserved = self._reserved_area_for_bbox(
                    bbox, position, max_width, max_height, margin
                )
                rotation = variant.get("layout_rotation", 0)
                oblique_penalty = 0 if abs(rotation % 90) < 1e-6 else 1
                placements.append(
                    {
                        "group": variant,
                        "position": position,
                        "reserved_area": reserved,
                        "score": (
                            oblique_penalty,
                            0,
                            0,
                            reserved["max_y"],
                            reserved["max_x"],
                            position["y"],
                            position["x"],
                        ),
                    }
                )

        if not placements:
            return None

        placements.sort(key=lambda item: item["score"])
        return {
            "group": placements[0]["group"],
            "position": placements[0]["position"],
            "reserved_area": placements[0]["reserved_area"],
            "score": placements[0]["score"],
        }

    def _reserved_area_for_bbox(
        self,
        bbox: Dict,
        position: Dict,
        max_width: float,
        max_height: float,
        margin: float,
    ) -> Dict:
        return {
            "min_x": position["x"],
            "min_y": position["y"],
            "max_x": min(max_width, position["x"] + bbox["width"] + margin),
            "max_y": min(max_height, position["y"] + bbox["height"] + margin),
        }

    def _placed_page_geometry(
        self, placed_polygon_groups: List[Dict], margin: float
    ) -> Optional["Polygon"]:
        if not SHAPELY_AVAILABLE or not placed_polygon_groups:
            return None

        geometries = []
        for group in placed_polygon_groups:
            cache_key = id(group)
            geometry = self._collision_geometry_cache.get(cache_key)
            if geometry is None:
                geometry = self._merge_group_polygons(self._group_collision_polygons(group))
                if geometry is not None and not geometry.is_empty and margin > 0:
                    geometry = geometry.buffer(margin / 2.0)
                if geometry is not None:
                    self._collision_geometry_cache[cache_key] = geometry
            if geometry is not None and not geometry.is_empty:
                geometries.append(geometry)

        if not geometries:
            return None
        if len(geometries) == 1:
            return geometries[0]
        return unary_union(geometries)

    def _should_use_polygon_fit(self, group: Dict, bbox: Dict) -> bool:
        if not SHAPELY_AVAILABLE:
            return False
        cache_key = id(group)
        cached = self._polygon_fit_cache.get(cache_key)
        if cached is not None:
            return cached
        bbox_area = bbox["width"] * bbox["height"]
        if bbox_area <= 1e-9:
            self._polygon_fit_cache[cache_key] = False
            return False
        geometry = self._merge_group_polygons(self._group_collision_polygons(group))
        if geometry is None or geometry.is_empty:
            self._polygon_fit_cache[cache_key] = False
            return False
        result = geometry.area / bbox_area < 0.85
        self._polygon_fit_cache[cache_key] = result
        return result

    def _group_collision_polygons(
        self, group: Dict
    ) -> List[List[Tuple[float, float]]]:
        return list(group.get("polygons", [])) + list(group.get("tabs", []))

    def _polygon_candidate_positions(
        self,
        bbox: Dict,
        occupied_areas: List[Dict],
        max_width: float,
        max_height: float,
    ) -> List[Dict]:
        max_x = max_width - bbox["width"]
        max_y = max_height - bbox["height"]
        if max_x < -1e-6 or max_y < -1e-6:
            return []

        x_candidates = {0.0, round(max_x, 6)}
        y_candidates = {0.0, round(max_y, 6)}
        for area in occupied_areas:
            x_candidates.update(
                [
                    round(area["min_x"], 6),
                    round(area["max_x"], 6),
                    round(area["min_x"] - bbox["width"], 6),
                    round(area["max_x"] - bbox["width"], 6),
                ]
            )
            y_candidates.update(
                [
                    round(area["min_y"], 6),
                    round(area["max_y"], 6),
                    round(area["min_y"] - bbox["height"], 6),
                    round(area["max_y"] - bbox["height"], 6),
                ]
            )

        positions = []
        for x in sorted(x_candidates):
            if x < -1e-6 or x > max_x + 1e-6:
                continue
            for y in sorted(y_candidates):
                if y < -1e-6 or y > max_y + 1e-6:
                    continue
                positions.append({"x": round(max(0.0, x), 6), "y": round(max(0.0, y), 6)})

        if len(occupied_areas) <= 10:
            return positions

        positions.sort(
            key=lambda position: (
                position["y"] + bbox["height"],
                position["x"] + bbox["width"],
                position["y"],
                position["x"],
            )
        )
        return positions[:128]

    def _polygon_position_fits_in_page(
        self,
        group: Dict,
        bbox: Dict,
        position: Dict,
        placed_geometry: "Polygon",
        max_width: float,
        max_height: float,
        margin: float,
        prepared_geometry=None,
    ) -> bool:
        if not SHAPELY_AVAILABLE:
            return False

        actual_area = {
            "min_x": position["x"],
            "min_y": position["y"],
            "max_x": position["x"] + bbox["width"],
            "max_y": position["y"] + bbox["height"],
        }
        if actual_area["max_x"] > max_width + 1e-6:
            return False
        if actual_area["max_y"] > max_height + 1e-6:
            return False

        cache_key = (id(group), round(margin, 6))
        candidate_geometry = self._buffered_collision_geometry_cache.get(cache_key)
        if candidate_geometry is None:
            candidate_geometry = self._merge_group_polygons(
                self._group_collision_polygons(group)
            )
            if candidate_geometry is None or candidate_geometry.is_empty:
                return False
            if margin > 0:
                candidate_geometry = candidate_geometry.buffer(margin / 2.0)
            self._buffered_collision_geometry_cache[cache_key] = candidate_geometry

        offset_x = position["x"] - bbox["min_x"]
        offset_y = position["y"] - bbox["min_y"]
        candidate_geometry = affinity.translate(
            candidate_geometry, xoff=offset_x, yoff=offset_y
        )

        intersects = (
            prepared_geometry.intersects(candidate_geometry)
            if prepared_geometry is not None
            else candidate_geometry.intersects(placed_geometry)
        )
        if not intersects:
            return True

        intersection = candidate_geometry.intersection(placed_geometry)
        return intersection.is_empty or intersection.area <= 1e-6

    def _sorted_free_areas(self, free_areas: List[Dict]) -> List[Dict]:
        return sorted(
            free_areas,
            key=lambda area: (
                area["min_y"],
                area["min_x"],
                -self._area_width(area) * self._area_height(area),
            ),
        )

    def _candidate_positions_in_free_area(
        self, bbox: Dict, free_area: Dict
    ) -> List[Dict]:
        width = bbox["width"]
        height = bbox["height"]
        candidates = {
            (free_area["min_x"], free_area["min_y"]),
            (free_area["max_x"] - width, free_area["min_y"]),
            (free_area["min_x"], free_area["max_y"] - height),
        }
        positions = []
        for x, y in candidates:
            positions.append({"x": round(max(0.0, x), 6), "y": round(max(0.0, y), 6)})
        return positions

    def _position_fits_in_page(
        self,
        bbox: Dict,
        position: Dict,
        free_area: Dict,
        occupied_areas: List[Dict],
        max_width: float,
        max_height: float,
        margin: float,
    ) -> bool:
        actual_area = {
            "min_x": position["x"],
            "min_y": position["y"],
            "max_x": position["x"] + bbox["width"],
            "max_y": position["y"] + bbox["height"],
        }
        if actual_area["max_x"] > max_width + 1e-6:
            return False
        if actual_area["max_y"] > max_height + 1e-6:
            return False
        if not self._area_contains(free_area, actual_area):
            return False

        reserved_area = self._reserved_area_for_bbox(
            bbox, position, max_width, max_height, margin
        )
        return not self._areas_overlap(reserved_area, occupied_areas)

    def _split_free_areas(self, free_areas: List[Dict], used_area: Dict) -> List[Dict]:
        split_areas = []
        for free_area in free_areas:
            if not self._areas_intersect(free_area, used_area):
                split_areas.append(free_area)
                continue

            clipped = self._clip_area_to_area(used_area, free_area)
            if clipped["min_x"] > free_area["min_x"] + 1e-6:
                split_areas.append(
                    {
                        "min_x": free_area["min_x"],
                        "min_y": free_area["min_y"],
                        "max_x": clipped["min_x"],
                        "max_y": free_area["max_y"],
                    }
                )
            if clipped["max_x"] < free_area["max_x"] - 1e-6:
                split_areas.append(
                    {
                        "min_x": clipped["max_x"],
                        "min_y": free_area["min_y"],
                        "max_x": free_area["max_x"],
                        "max_y": free_area["max_y"],
                    }
                )
            if clipped["min_y"] > free_area["min_y"] + 1e-6:
                split_areas.append(
                    {
                        "min_x": free_area["min_x"],
                        "min_y": free_area["min_y"],
                        "max_x": free_area["max_x"],
                        "max_y": clipped["min_y"],
                    }
                )
            if clipped["max_y"] < free_area["max_y"] - 1e-6:
                split_areas.append(
                    {
                        "min_x": free_area["min_x"],
                        "min_y": clipped["max_y"],
                        "max_x": free_area["max_x"],
                        "max_y": free_area["max_y"],
                    }
                )

        return self._prune_free_areas(split_areas)

    def _prune_free_areas(self, free_areas: List[Dict]) -> List[Dict]:
        useful_areas = [
            area
            for area in free_areas
            if self._area_width(area) > 1e-6 and self._area_height(area) > 1e-6
        ]
        pruned = []
        for index, area in enumerate(useful_areas):
            contained = False
            for other_index, other in enumerate(useful_areas):
                if index == other_index:
                    continue
                if self._area_contains(other, area):
                    contained = True
                    break
            if not contained and area not in pruned:
                pruned.append(area)
        return pruned

    def _areas_intersect(self, area1: Dict, area2: Dict) -> bool:
        return not (
            area1["max_x"] <= area2["min_x"] + 1e-6
            or area1["min_x"] >= area2["max_x"] - 1e-6
            or area1["max_y"] <= area2["min_y"] + 1e-6
            or area1["min_y"] >= area2["max_y"] - 1e-6
        )

    def _clip_area_to_area(self, area: Dict, bounds: Dict) -> Dict:
        return {
            "min_x": max(area["min_x"], bounds["min_x"]),
            "min_y": max(area["min_y"], bounds["min_y"]),
            "max_x": min(area["max_x"], bounds["max_x"]),
            "max_y": min(area["max_y"], bounds["max_y"]),
        }

    def _area_contains(self, outer: Dict, inner: Dict) -> bool:
        return (
            outer["min_x"] <= inner["min_x"] + 1e-6
            and outer["min_y"] <= inner["min_y"] + 1e-6
            and outer["max_x"] >= inner["max_x"] - 1e-6
            and outer["max_y"] >= inner["max_y"] - 1e-6
        )

    def _area_width(self, area: Dict) -> float:
        return area["max_x"] - area["min_x"]

    def _area_height(self, area: Dict) -> float:
        return area["max_y"] - area["min_y"]

    def _find_position_in_page(
        self,
        bbox: Dict,
        occupied_areas: List[Dict],
        max_width: float,
        max_height: float,
        margin: float,
    ) -> Optional[Dict]:
        """
        ページ内で重複しない位置を探索。
        STRtreeを使用して高速な空間検索を実行。

        Args:
            bbox: 配置するグループの境界ボックス
            occupied_areas: 既に占有されている領域のリスト
            max_width: ページの最大幅
            max_height: ページの最大高さ
            margin: マージン

        Returns:
            配置位置またはNone（配置不可の場合）
        """
        max_y = max_height - bbox["height"]
        max_x = max_width - bbox["width"]
        if max_x < -1e-6 or max_y < -1e-6:
            return None

        for x, y in self._candidate_page_positions(
            occupied_areas, max_x=max_x, max_y=max_y
        ):
            candidate_area = {
                "min_x": x,
                "min_y": y,
                "max_x": x + bbox["width"],
                "max_y": y + bbox["height"],
            }
            if not self._areas_overlap(candidate_area, occupied_areas):
                return {"x": x, "y": y}

        return None  # 配置可能な位置が見つからない

    def _candidate_page_positions(
        self, occupied_areas: List[Dict], max_x: float, max_y: float
    ) -> List[Tuple[float, float]]:
        """
        bottom-left配置の候補点を作る。
        既存矩形の右辺・下辺からできる空き角を優先し、紙面内の候補だけ返す。
        """
        candidates = {(0.0, 0.0)}
        x_edges = {0.0}
        y_edges = {0.0}

        for area in occupied_areas:
            x_values = [max(0.0, area["min_x"]), max(0.0, area["max_x"])]
            y_values = [max(0.0, area["min_y"]), max(0.0, area["max_y"])]

            for x in x_values:
                if x <= max_x + 1e-6:
                    x_edges.add(round(x, 6))
            for y in y_values:
                if y <= max_y + 1e-6:
                    y_edges.add(round(y, 6))

            corner_candidates = [
                (area["max_x"], area["min_y"]),
                (area["min_x"], area["max_y"]),
                (area["max_x"], area["max_y"]),
                (area["max_x"], 0.0),
                (0.0, area["max_y"]),
            ]
            for x, y in corner_candidates:
                x = max(0.0, round(x, 6))
                y = max(0.0, round(y, 6))
                if x <= max_x + 1e-6 and y <= max_y + 1e-6:
                    candidates.add((x, y))

        # 少数のエッジ同士も組み合わせ、棚配置だけでは届かない空きに入れる。
        if len(x_edges) * len(y_edges) <= 900:
            for x in x_edges:
                for y in y_edges:
                    if x <= max_x + 1e-6 and y <= max_y + 1e-6:
                        candidates.add((x, y))

        return sorted(candidates, key=lambda point: (point[1], point[0]))

    def update_scale_factor(self, scale_factor: float):
        """
        スケール倍率を更新

        Args:
            scale_factor: 新しいスケール倍率
        """
        self.scale_factor = scale_factor

    def update_page_settings(
        self, page_format: Optional[str] = None, page_orientation: Optional[str] = None
    ):
        """
        ページ設定を更新

        Args:
            page_format: ページフォーマット
            page_orientation: ページ方向
        """
        if page_format is not None:
            self.page_format = page_format
        if page_orientation is not None:
            self.page_orientation = page_orientation
        self._calculate_page_dimensions()
