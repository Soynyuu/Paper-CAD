"""
Layout Manager for BREP Papercraft Unfolding

This module handles the layout and positioning of unfolded groups on the output canvas.
It provides functionality for:
- Calculating bounding boxes for groups and overall layout
- Optimizing group placement to minimize paper usage
- Translating groups to their final positions
- Polygon-level overlap detection for accurate placement
"""

from typing import List, Dict, Tuple, Optional
try:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    print("Warning: Shapely not available. Using bounding box overlap detection only.")


class LayoutManager:
    """
    管理展開済みグループの配置とレイアウト最適化を行うクラス。
    重複回避・用紙サイズ最適化・効率的な配置アルゴリズムを提供。
    """
    
    def __init__(self, scale_factor: float = 10.0, page_format: str = "A4",
                 page_orientation: str = "portrait"):
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
            "Letter": {"width": 216, "height": 279}
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
            bbox = self._calculate_group_bbox(group["polygons"])
            group["bbox"] = bbox
        
        # 面積の大きい順にソート
        unfolded_groups.sort(key=lambda g: g["bbox"]["width"] * g["bbox"]["height"], reverse=True)
        
        # A4印刷エリアに収まるよう配置
        page_size = self.page_sizes_mm[self.page_format]
        printable_width = page_size["width"] - 2 * self.print_margin_mm
        printable_height = page_size["height"] - 2 * self.print_margin_mm - 25  # タイトル分
        
        print(f"印刷可能領域: {printable_width} x {printable_height} mm")
        
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
                "max_y": position["y"] + bbox["height"] + margin_mm
            }
            occupied_areas.append(occupied_area)
            
            print(f"グループ配置: ({position['x']:.1f}, {position['y']:.1f}) サイズ: {bbox['width']:.1f}x{bbox['height']:.1f}mm")
        
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
        
        return translated_group
    
    def _create_shapely_polygon(self, polygon_points: List[Tuple[float, float]]) -> Optional['Polygon']:
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
            print(f"ポリゴン作成エラー: {e}")
            return None
    
    def _polygons_overlap(self, polygons1: List[List[Tuple[float, float]]], 
                         polygons2: List[List[Tuple[float, float]]],
                         offset1: Tuple[float, float] = (0, 0),
                         offset2: Tuple[float, float] = (0, 0)) -> bool:
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
                    if intersection.area > 1e-6 or poly1.contains(poly2) or poly2.contains(poly1):
                        return True
        
        return False
    
    def _find_non_overlapping_position_with_polygons(
        self, group: Dict, bbox: Dict, occupied_areas: List[Dict], 
        placed_polygon_groups: List[Dict], margin_mm: float
    ) -> Dict:
        """
        他のグループと重複しない配置位置を探索（ポリゴンレベルの判定付き）。
        
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
        
        for y in range(0, max_y, grid_step):
            for x in range(0, max_x, grid_step):
                candidate_area = {
                    "min_x": x,
                    "min_y": y,
                    "max_x": x + bbox["width"],
                    "max_y": y + bbox["height"]
                }
                
                # まずbboxレベルで重複チェック（高速）
                if self._areas_overlap(candidate_area, occupied_areas):
                    continue
                
                # bboxが重複しない場合、ポリゴンレベルでチェック（精密）
                candidate_offset = (x - bbox["min_x"], y - bbox["min_y"])
                overlap_found = False
                
                if SHAPELY_AVAILABLE and placed_polygon_groups:
                    for placed_group in placed_polygon_groups:
                        if self._polygons_overlap(
                            group["polygons"], 
                            placed_group["polygons"],
                            candidate_offset,
                            (0, 0)  # placed_groupは既に配置済み
                        ):
                            overlap_found = True
                            break
                
                if not overlap_found:
                    return {"x": x, "y": y}
        
        # 重複しない位置が見つからない場合は右端に配置
        rightmost_x = max([area["max_x"] for area in occupied_areas], default=0)
        return {"x": rightmost_x + margin_mm, "y": 0}
    
    def _find_non_overlapping_position(self, bbox: Dict, occupied_areas: List[Dict], margin_mm: float) -> Dict:
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
                    "max_y": y + bbox["height"]
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
            if not (candidate["max_x"] <= occupied["min_x"] or 
                   candidate["min_x"] >= occupied["max_x"] or
                   candidate["max_y"] <= occupied["min_y"] or 
                   candidate["min_y"] >= occupied["max_y"]):
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
            0.1: "1/10"
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

    def layout_for_pages(self, unfolded_groups: List[Dict]) -> Tuple[List[List[Dict]], List[Dict]]:
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

        # 各グループの境界ボックス計算
        for group in unfolded_groups:
            bbox = self._calculate_group_bbox(group["polygons"])
            group["bbox"] = bbox

        # ═══ 統一スケール計算：すべてのグループに対して最小スケールを適用 ═══
        # すべてのグループをスキャンして、最も厳しいスケール制約（最小スケール）を計算
        # これにより、複数の建物を展開した際にすべてのパーツが同じスケールになり、組み立てが可能になる
        unified_scale = 1.0  # デフォルトはスケール調整なし
        max_width = 0.0  # 最大の横幅を記録

        for group in unfolded_groups:
            bbox = group["bbox"]
            # 縦幅は複数ページに分割するため、横幅のみをチェック
            if bbox["width"] > self.printable_width_mm:
                required_scale = self.printable_width_mm / bbox["width"]
                if required_scale < unified_scale:
                    unified_scale = required_scale
                    max_width = bbox["width"]

        # 統一スケールが必要な場合、すべてのグループに適用
        if unified_scale < 1.0:
            print(f"統一スケール調整: {unified_scale:.3f}（最大横幅: {max_width:.1f}mm）")
            print(f"すべてのグループに同じスケールを適用して、組み立て可能な模型を生成します")

            # 元のサイズを記録（警告用）
            original_total_width = max_width
            original_total_height = max([g["bbox"]["height"] for g in unfolded_groups])

            # すべてのグループに統一スケールを適用
            for group in unfolded_groups:
                # ポリゴンをスケール
                scaled_polygons = []
                for polygon in group["polygons"]:
                    scaled_polygon = [(x * unified_scale, y * unified_scale) for x, y in polygon]
                    scaled_polygons.append(scaled_polygon)
                group["polygons"] = scaled_polygons

                # タブをスケール
                scaled_tabs = []
                for tab in group.get("tabs", []):
                    scaled_tab = [(x * unified_scale, y * unified_scale) for x, y in tab]
                    scaled_tabs.append(scaled_tab)
                group["tabs"] = scaled_tabs

                # 境界ボックスを再計算
                bbox = self._calculate_group_bbox(group["polygons"])
                group["bbox"] = bbox

            print(f"  -> 全グループをスケール調整完了")

            # スケール比率を分数形式に変換（例: 0.633 → "約1/2" or "1/1.6"）
            # ユーザーフレンドリーな表記のため、一般的な分数に近い値を選択
            scale_ratio_text = self._format_scale_as_fraction(unified_scale)
            scale_percentage = int(unified_scale * 100)

            # 警告情報を追加
            warnings.append({
                "type": "unified_scale_applied",
                "message": (
                    f"📐 用紙サイズに合わせて、すべての建物を{scale_ratio_text}（{scale_percentage}%）に縮小しました。\n"
                    f"   すべてのパーツが同じ縮尺なので、組み立てが可能です。\n\n"
                    f"📐 All buildings scaled to {scale_ratio_text} ({scale_percentage}%) to fit the page.\n"
                    f"   All parts share the same scale for assembly compatibility."
                ),
                "details": {
                    "original_max_width_mm": round(original_total_width, 1),
                    "original_max_height_mm": round(original_total_height, 1),
                    "unified_scale_factor": round(unified_scale, 3),
                    "scale_ratio_text": scale_ratio_text,
                    "scale_percentage": scale_percentage,
                    "page_format": self.page_format,
                    "page_orientation": self.page_orientation,
                    "printable_area_mm": {
                        "width": self.printable_width_mm,
                        "height": self.printable_height_mm
                    }
                }
            })

        # 縦幅が印刷可能エリアを超える場合は情報メッセージ
        for group in unfolded_groups:
            bbox = group["bbox"]
            if bbox["height"] > self.printable_height_mm:
                print(f"情報: グループ縦幅({bbox['height']:.1f}mm)が印刷可能エリア({self.printable_height_mm}mm)を超えています")
                print(f"  -> 複数ページに分割されます")

        # 面積の大きい順にソート
        unfolded_groups.sort(key=lambda g: g["bbox"]["width"] * g["bbox"]["height"], reverse=True)
        
        # ページ単位で配置
        paged_groups = []
        current_page = []
        page_occupied_areas = []
        margin_mm = 5  # ページ内のアイテム間マージン
        
        for group in unfolded_groups:
            bbox = group["bbox"]
            
            # 現在のページに配置を試みる
            position = self._find_position_in_page(
                bbox, page_occupied_areas, 
                self.printable_width_mm, self.printable_height_mm, margin_mm
            )
            
            if position is None:
                # 現在のページに収まらない場合、新しいページを開始
                if current_page:
                    paged_groups.append(current_page)
                    current_page = []
                    page_occupied_areas = []
                
                # 新しいページの最初に配置
                position = {"x": 0, "y": 0}
            
            # グループを配置
            offset_x = position["x"] - bbox["min_x"]
            offset_y = position["y"] - bbox["min_y"]
            
            positioned_group = self._translate_group(group, offset_x, offset_y)
            positioned_group["position"] = position
            current_page.append(positioned_group)
            
            # 占有エリアを記録
            occupied_area = {
                "min_x": position["x"] - margin_mm,
                "min_y": position["y"] - margin_mm,
                "max_x": position["x"] + bbox["width"] + margin_mm,
                "max_y": position["y"] + bbox["height"] + margin_mm
            }
            page_occupied_areas.append(occupied_area)
        
        # 最後のページを追加
        if current_page:
            paged_groups.append(current_page)

        print(f"ページレイアウト完了: {len(paged_groups)}ページに分割")
        return paged_groups, warnings

    def _find_position_in_page(self, bbox: Dict, occupied_areas: List[Dict],
                               max_width: float, max_height: float,
                               margin: float) -> Optional[Dict]:
        """
        ページ内で重複しない位置を探索。
        
        Args:
            bbox: 配置するグループの境界ボックス
            occupied_areas: 既に占有されている領域のリスト
            max_width: ページの最大幅
            max_height: ページの最大高さ
            margin: マージン
        
        Returns:
            配置位置またはNone（配置不可の場合）
        """
        # グリッドベースで位置を探索
        grid_step = 5  # 5mm刻み
        
        for y in range(0, int(max_height - bbox["height"]), grid_step):
            for x in range(0, int(max_width - bbox["width"]), grid_step):
                candidate_area = {
                    "min_x": x,
                    "min_y": y,
                    "max_x": x + bbox["width"],
                    "max_y": y + bbox["height"]
                }
                
                # 既存エリアとの重複チェック
                if not self._areas_overlap(candidate_area, occupied_areas):
                    return {"x": x, "y": y}
        
        return None  # 配置可能な位置が見つからない

    def update_scale_factor(self, scale_factor: float):
        """
        スケール倍率を更新
        
        Args:
            scale_factor: 新しいスケール倍率
        """
        self.scale_factor = scale_factor
    
    def update_page_settings(self, page_format: Optional[str] = None,
                           page_orientation: Optional[str] = None):
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