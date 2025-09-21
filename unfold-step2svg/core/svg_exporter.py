import os
import tempfile
import uuid
from typing import List, Dict, Optional
import svgwrite


class SVGExporter:
    """
    SVG出力を専門とする独立したクラス。
    展開図のSVG形式での出力機能を提供。
    """
    
    def __init__(self, scale_factor: float = 10.0, units: str = "mm", 
                 tab_width: float = 5.0, show_scale: bool = True,
                 show_fold_lines: bool = True, show_cut_lines: bool = True,
                 page_format: str = "A4", layout_mode: str = "canvas",
                 page_orientation: str = "portrait"):
        """
        SVGExporterを初期化。
        
        Args:
            scale_factor: スケール倍率
            units: 単位系
            tab_width: タブ幅
            show_scale: スケールバーを表示するか
            show_fold_lines: 折り線を表示するか
            show_cut_lines: 切断線を表示するか
            page_format: ページフォーマット (A4, A3, Letter)
            layout_mode: レイアウトモード ("canvas" or "paged")
            page_orientation: ページ方向 ("portrait" or "landscape")
        """
        self.scale_factor = scale_factor
        self.units = units
        self.tab_width = tab_width
        self.show_scale = show_scale
        self.show_fold_lines = show_fold_lines
        self.show_cut_lines = show_cut_lines
        self.page_format = page_format
        self.layout_mode = layout_mode
        self.page_orientation = page_orientation
        
        # ページサイズの定義 (mm単位)
        self.page_sizes_mm = {
            "A4": {"width": 210, "height": 297},
            "A3": {"width": 297, "height": 420},
            "Letter": {"width": 216, "height": 279}
        }
        
        # ピクセル変換係数 (96 DPI)
        self.mm_to_px = 3.78
        
        # 印刷マージン (mm)
        self.print_margin_mm = 10

        # 現在のページサイズを計算
        self._calculate_page_dimensions()

        # テクスチャマッピング情報
        self.texture_mappings: List[Dict] = []
        # [{faceNumber: int, patternId: str, tileCount: int}, ...]

    def set_texture_mappings(self, texture_mappings: List[Dict]):
        """
        テクスチャマッピング情報を設定する。

        Args:
            texture_mappings: [{faceNumber: int, patternId: str, tileCount: int}, ...]
        """
        self.texture_mappings = texture_mappings
        print(f"[SVGExporter] Set {len(texture_mappings)} texture mappings")

    def export_to_svg(self, placed_groups: List[Dict], output_path: str,
                     layout_manager=None) -> str:
        """
        配置済み展開図をSVG形式で出力。
        商用品質の印刷対応（スケールバー・図面枠・注記等）。
        
        Args:
            placed_groups: 配置済みのグループデータ
            output_path: 出力パス
            layout_manager: レイアウトマネージャー（境界ボックス計算用）
        
        Returns:
            str: 出力されたSVGファイルのパス
        """
        if not placed_groups:
            raise ValueError("出力する展開図データがありません")
        
        # 全体境界ボックス計算
        if layout_manager:
            overall_bbox = layout_manager.calculate_overall_bbox(placed_groups)
        else:
            overall_bbox = self._calculate_overall_bbox(placed_groups)
        
        print(f"ページフォーマット: {self.page_format}")
        print(f"全体境界ボックス: {overall_bbox}")
        
        # scale_factorはAPIから渡される値を使用（自動調整しない）
        # scale_factor=150なら1/150スケール → 実際の描画倍率は基準倍率/scale_factor
        # 基準倍率を10とし、scale_factorで割る
        base_scale = 10.0  # 基準描画倍率
        actual_scale = base_scale / self.scale_factor if self.scale_factor > 0 else base_scale
        print(f"縮尺: 1/{self.scale_factor:.0f} (描画倍率: {actual_scale:.2f})")
        
        # SVGサイズを内容に合わせて動的調整
        scaled_content_width = overall_bbox["width"] * actual_scale
        scaled_content_height = overall_bbox["height"] * actual_scale
        
        # 十分な余白を確保
        margin = 50
        svg_width = scaled_content_width + 2 * margin
        svg_height = scaled_content_height + 2 * margin + 100  # タイトル・スケール用
        
        # 最小サイズを保証
        svg_width = max(svg_width, 600)
        svg_height = max(svg_height, 400)
        
        print(f"動的SVGサイズ: {svg_width:.1f} x {svg_height:.1f} px")
        
        # SVG作成 (内容に合わせたサイズ)
        dwg = svgwrite.Drawing(
            output_path, 
            size=(f"{svg_width}px", f"{svg_height}px"), 
            viewBox=f"0 0 {svg_width} {svg_height}"
        )
        
        # 商用グレードスタイル定義
        dwg.defs.add(dwg.style("""
            .face-polygon { fill: none; stroke: #000000; stroke-width: 2; }
            .face-polygon-textured { stroke: #000000; stroke-width: 2; }
            .tab-polygon { fill: none; stroke: #0066cc; stroke-width: 1.5; stroke-dasharray: 4,4; }
            .fold-line { stroke: #ff6600; stroke-width: 1; stroke-dasharray: 6,6; }
            .cut-line { stroke: #ff0000; stroke-width: 0.8; stroke-dasharray: 3,3; }
            .title-text { font-family: Arial, sans-serif; font-size: 24px; font-weight: bold; fill: #000000; }
            .scale-text { font-family: Arial, sans-serif; font-size: 16px; fill: #000000; }
            .note-text { font-family: Arial, sans-serif; font-size: 14px; fill: #666666; }
            .face-number { font-family: Arial, sans-serif; font-size: 140px; font-weight: bold; fill: #ff0000; text-anchor: middle; }
        """))

        # テクスチャパターンの定義を生成
        self._generate_texture_patterns(dwg, actual_scale)
        
        # メインコンテンツを適切にオフセット
        content_offset_x = margin - overall_bbox["min_x"] * actual_scale
        content_offset_y = margin + 60 - overall_bbox["min_y"] * actual_scale  # タイトル分下げる
        
        polygon_count = 0
        
        for group_idx, group in enumerate(placed_groups):
            print(f"グループ{group_idx}をSVGに描画中...")
            print(f"  ポリゴン数: {len(group['polygons'])}")
            
            # 面ポリゴン描画
            for poly_idx, polygon in enumerate(group["polygons"]):
                if len(polygon) >= 3:
                    # スケールファクターを適用
                    points = [(x * actual_scale + content_offset_x, y * actual_scale + content_offset_y) for x, y in polygon]

                    # 面番号を取得してテクスチャを確認
                    face_number = None
                    texture_mapping = None
                    if "face_numbers" in group and poly_idx < len(group["face_numbers"]):
                        face_number = group["face_numbers"][poly_idx]
                        # テクスチャマッピングを検索
                        for mapping in self.texture_mappings:
                            if mapping.get("faceNumber") == face_number:
                                texture_mapping = mapping
                                break

                    # テクスチャがある場合はパターンを適用
                    if texture_mapping:
                        pattern_id = f"pattern_{texture_mapping['patternId']}_{texture_mapping['tileCount']}"
                        dwg.add(dwg.polygon(
                            points=points,
                            class_="face-polygon-textured",
                            fill=f"url(#{pattern_id})"
                        ))
                        print(f"  ポリゴン{poly_idx}: {len(polygon)}点を描画（テクスチャ: {pattern_id}）")
                    else:
                        dwg.add(dwg.polygon(points=points, class_="face-polygon"))
                        print(f"  ポリゴン{poly_idx}: {len(polygon)}点を描画")

                    polygon_count += 1
                    
                    # 面番号を描画（ポリゴンの中心に配置）
                    print(f"  グループデータ: face_numbers={group.get('face_numbers', 'なし')}")
                    if "face_numbers" in group and poly_idx < len(group["face_numbers"]):
                        # ポリゴンの中心を計算
                        center_x = sum(p[0] for p in points) / len(points)
                        center_y = sum(p[1] for p in points) / len(points)
                        
                        # 面のサイズに基づいてフォントサイズを計算
                        font_size = self._calculate_face_number_size(points)
                        
                        # 面番号テキストを追加（動的サイズで）
                        face_number = group["face_numbers"][poly_idx]
                        dwg.add(dwg.text(
                            str(face_number),
                            insert=(center_x, center_y),
                            style=f"font-family: Arial, sans-serif; font-size: {font_size}px; font-weight: bold; fill: #ff0000; text-anchor: middle;",
                            dominant_baseline="middle"  # 垂直中央揃え
                        ))
                        print(f"    面番号{face_number}を中心({center_x:.1f}, {center_y:.1f})にサイズ{font_size:.1f}pxで描画")
                    else:
                        print(f"    面番号なし: poly_idx={poly_idx}, face_numbers存在={('face_numbers' in group)}")
                else:
                    print(f"  ポリゴン{poly_idx}: 点数不足({len(polygon)}点)")
            
            # タブ描画
            for tab_idx, tab in enumerate(group.get("tabs", [])):
                if len(tab) >= 3:
                    # スケールファクターを適用
                    points = [(x * actual_scale + content_offset_x, y * actual_scale + content_offset_y) for x, y in tab]
                    dwg.add(dwg.polygon(points=points, class_="tab-polygon"))
                    print(f"  タブ{tab_idx}: {len(tab)}点を描画")
        
        print(f"SVG描画完了: {polygon_count}個のポリゴンを描画")
        
        # タイトル描画 (ページ上部中央)
        title = f"Diorama-CAD(mitou-jr) - {len(placed_groups)} Groups"
        title_x = svg_width / 2
        title_y = 40
        dwg.add(dwg.text(title, insert=(title_x, title_y), text_anchor="middle", class_="title-text"))
        
        # スケールバー描画（actual_scaleを渡す）
        self._add_scale_bar_with_scale(dwg, svg_width, svg_height, actual_scale)
        
        # 注記追加
        self._add_technical_notes(dwg, svg_width, svg_height)
        
        # SVG保存
        dwg.save()
        return output_path
    
    def _add_scale_bar_with_scale(self, dwg, svg_width: float, svg_height: float, actual_scale: float):
        """動的サイズ用スケールバー追加"""
        # スケールバー仕様
        bar_length_mm = 50.0  # 50mm (5cm)
        bar_length_px = bar_length_mm * actual_scale / 10  # スケールに合わせて調整
        
        # 配置位置 (左下)
        bar_x = 50
        bar_y = svg_height - 50
        
        # スケールバー本体
        dwg.add(dwg.line(start=(bar_x, bar_y), end=(bar_x + bar_length_px, bar_y),
                        stroke='black', stroke_width=2))
        
        # 目盛り
        dwg.add(dwg.line(start=(bar_x, bar_y - 6), end=(bar_x, bar_y + 6),
                        stroke='black', stroke_width=1.5))
        dwg.add(dwg.line(start=(bar_x + bar_length_px, bar_y - 6), 
                        end=(bar_x + bar_length_px, bar_y + 6),
                        stroke='black', stroke_width=1.5))
        
        # ラベル
        scale_text = f"{bar_length_mm:.0f} mm"
        dwg.add(dwg.text(scale_text, insert=(bar_x + bar_length_px/2, bar_y - 12),
                        text_anchor="middle", class_="scale-text"))

    def _calculate_polygon_area(self, points):
        """
        ポリゴンの面積を計算（Shoelace formula）
        
        Args:
            points: ポリゴンの頂点リスト [(x, y), ...]
            
        Returns:
            面積（絶対値）
        """
        n = len(points)
        if n < 3:
            return 0
        
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        
        return abs(area) / 2
    
    def _generate_texture_patterns(self, dwg, actual_scale):
        """
        テクスチャパターンをSVGのdefs要素に追加する。

        Args:
            dwg: SVG Drawing object
            actual_scale: 実際の描画スケール
        """
        if not self.texture_mappings:
            return

        # ユニークなパターンIDのセットを作成
        unique_patterns = {}
        for mapping in self.texture_mappings:
            pattern_id = f"pattern_{mapping['patternId']}_{mapping['tileCount']}"
            if pattern_id not in unique_patterns:
                unique_patterns[pattern_id] = {
                    'patternId': mapping['patternId'],
                    'tileCount': mapping['tileCount']
                }

        # 各ユニークパターンをdefsに追加
        for pattern_id, pattern_info in unique_patterns.items():
            # パターンサイズを計算（タイル数に基づく）
            tile_size = 100 / pattern_info['tileCount'] # 基本サイズを分割

            # パターン定義
            pattern = dwg.pattern(
                id=pattern_id,
                size=(f"{tile_size}%", f"{tile_size}%"),
                patternUnits="objectBoundingBox"
            )

            # パターンごとに異なる簡易的なデザインを追加
            if pattern_info['patternId'] == 'brick':
                # レンガパターン
                pattern.add(dwg.rect((0, 0), ('100%', '100%'), fill='#8B4513'))
                pattern.add(dwg.rect((0, 0), ('95%', '45%'), fill='#A0522D'))
                pattern.add(dwg.rect((5, '55%'), ('95%', '40%'), fill='#A0522D'))
            elif pattern_info['patternId'] == 'wood':
                # 木目パターン
                pattern.add(dwg.rect((0, 0), ('100%', '100%'), fill='#8B6F47'))
                pattern.add(dwg.line((0, '25%'), ('100%', '25%'), stroke='#6F5B3E', stroke_width=1))
                pattern.add(dwg.line((0, '50%'), ('100%', '50%'), stroke='#6F5B3E', stroke_width=1))
                pattern.add(dwg.line((0, '75%'), ('100%', '75%'), stroke='#6F5B3E', stroke_width=1))
            elif pattern_info['patternId'] == 'stone':
                # 石パターン
                pattern.add(dwg.rect((0, 0), ('100%', '100%'), fill='#808080'))
                pattern.add(dwg.circle(('30%', '30%'), r='15%', fill='#696969'))
                pattern.add(dwg.circle(('70%', '70%'), r='10%', fill='#696969'))
            else:
                # デフォルトパターン（グリッド）
                pattern.add(dwg.rect((0, 0), ('100%', '100%'), fill='#E0E0E0'))
                pattern.add(dwg.line((0, '50%'), ('100%', '50%'), stroke='#C0C0C0', stroke_width=1))
                pattern.add(dwg.line(('50%', 0), ('50%', '100%'), stroke='#C0C0C0', stroke_width=1))

            dwg.defs.add(pattern)
            print(f"[SVGExporter] Generated pattern: {pattern_id}")

    def _calculate_face_number_size(self, polygon_points):
        """
        面の大きさに基づいて適切なフォントサイズを計算

        Args:
            polygon_points: ポリゴンの頂点リスト（SVG座標系）

        Returns:
            適切なフォントサイズ（px）
        """
        if len(polygon_points) < 3:
            return 12  # デフォルトサイズを小さく

        # 境界ボックスを計算
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]

        bbox_width = max(xs) - min(xs)
        bbox_height = max(ys) - min(ys)
        
        # 最小辺長を取得
        min_dimension = min(bbox_width, bbox_height)
        
        # フォントサイズを面の最小辺の25%に設定（より控えめなサイズ）
        font_size = min_dimension * 0.25
        
        # 最小・最大サイズでクリップ（A4印刷向けに調整）
        # 最小: 10px（読める最小サイズ）
        # 最大: 48px（印刷向け上限）
        font_size = max(10, min(48, font_size))
        
        return font_size
    
    def _add_technical_notes(self, dwg, svg_width: float, svg_height: float):
        """動的サイズ用技術注記・凡例追加"""
        notes_x = svg_width - 250
        notes_y = svg_height - 80
        
        notes = [
            "切り取り線 (Cut Lines)",
            "━━━ 実線で切断",
        ]
        
        for i, note in enumerate(notes):
            dwg.add(dwg.text(note, insert=(notes_x, notes_y + i * 18), class_="note-text"))
    
    def _calculate_overall_bbox(self, placed_groups: List[Dict]) -> Dict:
        """
        全体境界ボックスを計算（layout_managerがない場合のフォールバック）
        """
        if not placed_groups:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for group in placed_groups:
            for polygon in group.get("polygons", []):
                for x, y in polygon:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
            
            for tab in group.get("tabs", []):
                for x, y in tab:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        
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
        
        # ピクセル変換
        self.page_width_px = self.page_width_mm * self.mm_to_px
        self.page_height_px = self.page_height_mm * self.mm_to_px
        
        # 印刷可能エリア計算
        self.printable_width_mm = self.page_width_mm - 2 * self.print_margin_mm
        self.printable_height_mm = self.page_height_mm - 2 * self.print_margin_mm
        self.printable_width_px = self.printable_width_mm * self.mm_to_px
        self.printable_height_px = self.printable_height_mm * self.mm_to_px

    def export_to_svg_paged_single_file(self, paged_groups: List[List[Dict]], output_path: str) -> str:
        """
        ページ単位で分割された展開図を単一のSVGファイルに出力。
        各ページを縦に並べて表示し、印刷時にページ区切りが明確になるようにする。
        
        Args:
            paged_groups: ページごとにグループ化された展開図データ
            output_path: 出力パス
        
        Returns:
            str: 出力されたSVGファイルのパス
        """
        if not paged_groups:
            raise ValueError("出力する展開図データがありません")
        
        # 全体のSVGサイズを計算（全ページを縦に並べる）
        total_height = self.page_height_px * len(paged_groups)
        page_gap = 20  # ページ間の隙間（視覚的区切り）
        total_height_with_gaps = total_height + page_gap * (len(paged_groups) - 1)
        
        # SVG作成（全ページを含む大きさ）
        dwg = svgwrite.Drawing(
            output_path,
            size=(f"{self.page_width_px}px", f"{total_height_with_gaps}px"),
            viewBox=f"0 0 {self.page_width_px} {total_height_with_gaps}"
        )
        
        # スタイル定義
        dwg.defs.add(dwg.style("""
            .face-polygon { fill: none; stroke: #000000; stroke-width: 2; }
            .tab-polygon { fill: none; stroke: #0066cc; stroke-width: 1.5; stroke-dasharray: 4,4; }
            .page-border { fill: white; stroke: #999999; stroke-width: 2; stroke-dasharray: 10,5; }
            .page-separator { stroke: #666666; stroke-width: 1; stroke-dasharray: 20,10; }
            .cut-mark { stroke: #000000; stroke-width: 0.5; }
            .page-number { font-family: Arial, sans-serif; font-size: 14px; fill: #333333; font-weight: bold; }
            .face-number { font-family: Arial, sans-serif; font-weight: bold; fill: #ff0000; text-anchor: middle; }
            .page-label { font-family: Arial, sans-serif; font-size: 12px; fill: #666666; }
        """))
        
        margin_px = self.print_margin_mm * self.mm_to_px
        
        # 各ページを描画
        for page_num, page_groups in enumerate(paged_groups, 1):
            # ページのY座標オフセット
            page_y_offset = (self.page_height_px + page_gap) * (page_num - 1)
            
            # ページ背景（白）と境界線
            dwg.add(dwg.rect(
                insert=(0, page_y_offset),
                size=(self.page_width_px, self.page_height_px),
                class_="page-border"
            ))
            
            # 印刷可能エリアの境界線
            dwg.add(dwg.rect(
                insert=(margin_px, page_y_offset + margin_px),
                size=(self.printable_width_px, self.printable_height_px),
                style="fill: none; stroke: #cccccc; stroke-width: 1; stroke-dasharray: 5,5;"
            ))
            
            # カットマークを追加（四隅）
            mark_length = 15
            corners = [
                (0, page_y_offset),
                (self.page_width_px, page_y_offset),
                (0, page_y_offset + self.page_height_px),
                (self.page_width_px, page_y_offset + self.page_height_px)
            ]
            
            for x, y in corners:
                # 横線
                dwg.add(dwg.line(
                    start=(x - mark_length if x > self.page_width_px/2 else x, y),
                    end=(x + mark_length if x < self.page_width_px/2 else x, y),
                    class_="cut-mark"
                ))
                # 縦線
                dwg.add(dwg.line(
                    start=(x, y - mark_length if y > page_y_offset + self.page_height_px/2 else y),
                    end=(x, y + mark_length if y < page_y_offset + self.page_height_px/2 else y),
                    class_="cut-mark"
                ))
            
            # グループを描画（mm単位の座標をpxに変換）
            for group in page_groups:
                # 面ポリゴン描画
                for poly_idx, polygon in enumerate(group.get("polygons", [])):
                    if len(polygon) >= 3:
                        # mm単位の座標をピクセルに変換（scale_factorは使わず、mm_to_pxで変換）
                        points = [
                            (x * self.mm_to_px + margin_px, 
                             y * self.mm_to_px + margin_px + page_y_offset) 
                            for x, y in polygon
                        ]
                        dwg.add(dwg.polygon(points=points, class_="face-polygon"))
                        
                        # 面番号を描画
                        if "face_numbers" in group and poly_idx < len(group["face_numbers"]):
                            center_x = sum(p[0] for p in points) / len(points)
                            center_y = sum(p[1] for p in points) / len(points)
                            font_size = self._calculate_face_number_size(points)
                            face_number = group["face_numbers"][poly_idx]
                            
                            dwg.add(dwg.text(
                                str(face_number),
                                insert=(center_x, center_y),
                                style=f"font-family: Arial, sans-serif; font-size: {font_size}px; font-weight: bold; fill: #ff0000; text-anchor: middle;",
                                dominant_baseline="middle"
                            ))
                
                # タブ描画
                for tab in group.get("tabs", []):
                    if len(tab) >= 3:
                        points = [
                            (x * self.mm_to_px + margin_px, 
                             y * self.mm_to_px + margin_px + page_y_offset) 
                            for x, y in tab
                        ]
                        dwg.add(dwg.polygon(points=points, class_="tab-polygon"))
            
            # ページ番号とフォーマット情報
            dwg.add(dwg.text(
                f"Page {page_num} / {len(paged_groups)} - {self.page_format} {self.page_orientation.capitalize()}",
                insert=(self.page_width_px / 2, page_y_offset + self.page_height_px - 10),
                text_anchor="middle",
                class_="page-number"
            ))
            
            # タイトル（各ページの上部）
            dwg.add(dwg.text(
                f"Diorama-CAD (mitou-jr)",
                insert=(self.page_width_px / 2, page_y_offset + 25),
                text_anchor="middle",
                style="font-family: Arial, sans-serif; font-size: 16px; fill: #000000; font-weight: bold;"
            ))
            
            # ページ区切り線（最後のページ以外）
            if page_num < len(paged_groups):
                separator_y = page_y_offset + self.page_height_px + page_gap / 2
                dwg.add(dwg.line(
                    start=(0, separator_y),
                    end=(self.page_width_px, separator_y),
                    class_="page-separator"
                ))
        
        # SVG保存
        dwg.save()
        print(f"単一SVGファイルに{len(paged_groups)}ページを出力: {output_path}")
        return output_path

    def export_to_svg_paged(self, paged_groups: List[List[Dict]], output_dir: str) -> List[str]:
        """
        ページ単位で分割された展開図をSVG形式で出力。
        各ページが印刷可能なサイズに収まるように配置。
        
        Args:
            paged_groups: ページごとにグループ化された展開図データ
            output_dir: 出力ディレクトリパス
        
        Returns:
            List[str]: 出力されたSVGファイルのパスリスト
        """
        if not paged_groups:
            raise ValueError("出力する展開図データがありません")
        
        svg_paths = []
        
        for page_num, page_groups in enumerate(paged_groups, 1):
            # 各ページのSVGを生成
            output_path = os.path.join(output_dir, f"page_{page_num:02d}.svg")
            
            # SVG作成 (印刷用固定サイズ)
            dwg = svgwrite.Drawing(
                output_path,
                size=(f"{self.page_width_px}px", f"{self.page_height_px}px"),
                viewBox=f"0 0 {self.page_width_px} {self.page_height_px}"
            )
            
            # ページ用スタイル定義
            dwg.defs.add(dwg.style("""
                .face-polygon { fill: none; stroke: #000000; stroke-width: 2; }
                .tab-polygon { fill: none; stroke: #0066cc; stroke-width: 1.5; stroke-dasharray: 4,4; }
                .page-border { fill: none; stroke: #cccccc; stroke-width: 1; stroke-dasharray: 10,5; }
                .cut-mark { stroke: #000000; stroke-width: 0.5; }
                .page-number { font-family: Arial, sans-serif; font-size: 12px; fill: #666666; }
                .face-number { font-family: Arial, sans-serif; font-weight: bold; fill: #ff0000; text-anchor: middle; }
            """))
            
            # ページ境界線を描画
            margin_px = self.print_margin_mm * self.mm_to_px
            dwg.add(dwg.rect(
                insert=(margin_px, margin_px),
                size=(self.printable_width_px, self.printable_height_px),
                class_="page-border"
            ))
            
            # scale_factorから実際の描画倍率を計算
            base_scale = 10.0  # 基準描画倍率
            actual_scale = base_scale / self.scale_factor if self.scale_factor > 0 else base_scale
            
            # カットマークを追加（四隅）
            mark_length = 10
            corners = [
                (margin_px, margin_px),
                (self.page_width_px - margin_px, margin_px),
                (margin_px, self.page_height_px - margin_px),
                (self.page_width_px - margin_px, self.page_height_px - margin_px)
            ]
            
            for x, y in corners:
                # 横線
                dwg.add(dwg.line(
                    start=(x - mark_length if x > self.page_width_px/2 else x, y),
                    end=(x + mark_length if x < self.page_width_px/2 else x, y),
                    class_="cut-mark"
                ))
                # 縦線
                dwg.add(dwg.line(
                    start=(x, y - mark_length if y > self.page_height_px/2 else y),
                    end=(x, y + mark_length if y < self.page_height_px/2 else y),
                    class_="cut-mark"
                ))
            
            # グループを描画
            for group in page_groups:
                # 面ポリゴン描画
                for poly_idx, polygon in enumerate(group.get("polygons", [])):
                    if len(polygon) >= 3:
                        # ページマージンを考慮した配置
                        points = [
                            (x * actual_scale + margin_px, 
                             y * actual_scale + margin_px) 
                            for x, y in polygon
                        ]
                        dwg.add(dwg.polygon(points=points, class_="face-polygon"))
                        
                        # 面番号を描画
                        if "face_numbers" in group and poly_idx < len(group["face_numbers"]):
                            center_x = sum(p[0] for p in points) / len(points)
                            center_y = sum(p[1] for p in points) / len(points)
                            font_size = self._calculate_face_number_size(points)
                            face_number = group["face_numbers"][poly_idx]
                            
                            dwg.add(dwg.text(
                                str(face_number),
                                insert=(center_x, center_y),
                                style=f"font-family: Arial, sans-serif; font-size: {font_size}px; font-weight: bold; fill: #ff0000; text-anchor: middle;",
                                dominant_baseline="middle"
                            ))
                
                # タブ描画
                for tab in group.get("tabs", []):
                    if len(tab) >= 3:
                        points = [
                            (x * actual_scale + margin_px, 
                             y * actual_scale + margin_px) 
                            for x, y in tab
                        ]
                        dwg.add(dwg.polygon(points=points, class_="tab-polygon"))
            
            # ページ番号を追加
            dwg.add(dwg.text(
                f"Page {page_num} / {len(paged_groups)}",
                insert=(self.page_width_px / 2, self.page_height_px - 20),
                text_anchor="middle",
                class_="page-number"
            ))
            
            # タイトルとプロジェクト情報
            dwg.add(dwg.text(
                f"Diorama-CAD (mitou-jr) - {self.page_format} {self.page_orientation.capitalize()}",
                insert=(self.page_width_px / 2, 20),
                text_anchor="middle",
                style="font-family: Arial, sans-serif; font-size: 14px; fill: #000000;"
            ))
            
            # SVG保存
            dwg.save()
            svg_paths.append(output_path)
            
            print(f"ページ {page_num} を出力: {output_path}")
        
        return svg_paths

    def update_settings(self, scale_factor: Optional[float] = None, 
                       units: Optional[str] = None, 
                       tab_width: Optional[float] = None,
                       show_scale: Optional[bool] = None,
                       show_fold_lines: Optional[bool] = None,
                       show_cut_lines: Optional[bool] = None,
                       layout_mode: Optional[str] = None,
                       page_format: Optional[str] = None,
                       page_orientation: Optional[str] = None):
        """
        設定を更新する
        """
        if scale_factor is not None:
            self.scale_factor = scale_factor
        if units is not None:
            self.units = units
        if tab_width is not None:
            self.tab_width = tab_width
        if show_scale is not None:
            self.show_scale = show_scale
        if show_fold_lines is not None:
            self.show_fold_lines = show_fold_lines
        if show_cut_lines is not None:
            self.show_cut_lines = show_cut_lines
        if layout_mode is not None:
            self.layout_mode = layout_mode
        if page_format is not None:
            self.page_format = page_format
            self._calculate_page_dimensions()
        if page_orientation is not None:
            self.page_orientation = page_orientation
            self._calculate_page_dimensions()