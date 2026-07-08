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
        rotated_group["bbox"] = self.calculate_group_bbox(rotated_group)
        rotated_group["layout_rotation"] = angle_degrees
        rotated_group.pop("_merged_geometry", None)
        return rotated_group

    def _layout_orientations(self, group: Dict) -> List[Dict]:
        """
        配置候補として複数の回転角を返す。
        """
        orientations = []
        seen_dimensions = set()
        for angle in range(0, 180, 15):
            rotated_group = self._rotate_group(group, float(angle))
            bbox = rotated_group["bbox"]
            key = (round(bbox["width"], 3), round(bbox["height"], 3))
            if key in seen_dimensions:
                continue
            seen_dimensions.add(key)
            orientations.append(rotated_group)

        return orientations

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

        return max(1.0, best_scale or 1.0)

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

        # 警告情報を収集するリスト
        warnings = []

        # 各グループの境界ボックス計算。
        # 縮尺はStepUnfoldGeneratorで紙上寸法へ変換済みのため、ここでは勝手に縮小しない。
        for group in unfolded_groups:
            bbox = self.calculate_group_bbox(group)
            group["bbox"] = bbox

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

        # 面積の大きい順にソート
        unfolded_groups.sort(
            key=lambda g: g["bbox"]["width"] * g["bbox"]["height"], reverse=True
        )

        # ページ単位で配置
        paged_groups = []
        current_page = []
        page_occupied_areas = []
        margin_mm = 5  # ページ内のアイテム間マージン

        for group in unfolded_groups:
            # 現在のページに配置を試みる
            placement = self._find_oriented_position_in_page(
                group,
                page_occupied_areas,
                self.printable_width_mm,
                self.printable_height_mm,
                margin_mm,
            )

            if placement is None:
                # 現在のページに収まらない場合、新しいページを開始
                if current_page:
                    paged_groups.append(current_page)
                    current_page = []
                    page_occupied_areas = []

                # 新しいページの最初に配置
                placement = self._first_page_position(group)

            variant = placement["group"]
            bbox = variant["bbox"]
            position = placement["position"]

            # グループを配置
            offset_x = position["x"] - bbox["min_x"]
            offset_y = position["y"] - bbox["min_y"]

            positioned_group = self._translate_group(variant, offset_x, offset_y)
            positioned_group["position"] = position
            positioned_group["layout_rotation"] = variant.get("layout_rotation", 0)
            current_page.append(positioned_group)

            # 占有エリアを記録
            occupied_area = {
                "min_x": position["x"] - margin_mm,
                "min_y": position["y"] - margin_mm,
                "max_x": position["x"] + bbox["width"] + margin_mm,
                "max_y": position["y"] + bbox["height"] + margin_mm,
            }
            page_occupied_areas.append(occupied_area)

        # 最後のページを追加
        if current_page:
            paged_groups.append(current_page)

        logger.info(f"ページレイアウト完了: {len(paged_groups)}ページに分割")
        return paged_groups, warnings

    def can_pack_groups_on_single_page(
        self, unfolded_groups: List[Dict], margin_mm: float = 5
    ) -> bool:
        """
        与えられた紙上寸法のグループ群が、選択用紙1枚に配置できるかを判定する。
        実際の配置と同じ向き候補・候補点探索を使う。
        """
        page_occupied_areas: List[Dict] = []

        groups = copy.deepcopy(unfolded_groups)
        for group in groups:
            group["bbox"] = self.calculate_group_bbox(group)

        groups.sort(
            key=lambda g: (
                max(g["bbox"]["width"], g["bbox"]["height"]),
                g["bbox"]["width"] * g["bbox"]["height"],
            ),
            reverse=True,
        )

        for group in groups:
            placement = self._find_oriented_position_in_page(
                group,
                page_occupied_areas,
                self.printable_width_mm,
                self.printable_height_mm,
                margin_mm,
            )
            if placement is None:
                return False

            bbox = placement["group"]["bbox"]
            position = placement["position"]
            page_occupied_areas.append(
                {
                    "min_x": position["x"] - margin_mm,
                    "min_y": position["y"] - margin_mm,
                    "max_x": position["x"] + bbox["width"] + margin_mm,
                    "max_y": position["y"] + bbox["height"] + margin_mm,
                }
            )

        return True

    def _first_page_position(self, group: Dict) -> Dict:
        orientations = self._layout_orientations(group)
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
        max_width: float,
        max_height: float,
        margin: float,
    ) -> Optional[Dict]:
        placements = []
        for variant in self._layout_orientations(group):
            position = self._find_position_in_page(
                variant["bbox"], occupied_areas, max_width, max_height, margin
            )
            if position is None:
                continue
            bbox = variant["bbox"]
            placements.append(
                {
                    "group": variant,
                    "position": position,
                    "score": (
                        position["y"] + bbox["height"],
                        position["x"] + bbox["width"],
                        position["y"],
                        position["x"],
                    ),
                }
            )

        if not placements:
            return None

        placements.sort(key=lambda item: item["score"])
        return {"group": placements[0]["group"], "position": placements[0]["position"]}

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
