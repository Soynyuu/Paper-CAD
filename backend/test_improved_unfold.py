#!/usr/bin/env python3
"""
改善された展開アルゴリズムのテストスクリプト
このスクリプトは、以下の改善点を検証します：
1. 境界線簡略化の精度向上
2. デフォルト境界線の動的生成
3. 投影アルゴリズムの安定性
4. 面グループ化の改善
"""

import sys
import os
import tempfile
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.unfold_engine import UnfoldEngine
from core.geometry_analyzer import GeometryAnalyzer
from services.step_processor import StepUnfoldGenerator
from models.request_models import UnfoldRequest


def test_boundary_simplification():
    """境界線簡略化の改善をテスト"""
    print("\n" + "=" * 60)
    print("テスト1: 境界線簡略化の改善")
    print("=" * 60)

    engine = UnfoldEngine()

    # テスト用の複雑な境界線（100点の多角形）
    import math
    points = []
    for i in range(100):
        angle = (2 * math.pi * i) / 100
        # 少し歪んだ円（実際には多角形）
        radius = 50 + 5 * math.sin(angle * 8)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append((x, y))

    # Douglas-Peucker簡略化をテスト
    print(f"元の点数: {len(points)}")

    # 異なる許容誤差でテスト
    for tolerance in [0.1, 0.5, 1.0, 2.0]:
        simplified = engine._douglas_peucker_simplification(points, tolerance)
        print(f"許容誤差 {tolerance}mm -> 簡略化後: {len(simplified)}点")

    print("✓ 境界線簡略化テスト完了")


def test_dynamic_boundary_generation():
    """動的境界線生成のテスト"""
    print("\n" + "=" * 60)
    print("テスト2: 動的境界線生成")
    print("=" * 60)

    analyzer = GeometryAnalyzer()

    # 異なるスケールの面データをテスト
    test_cases = [
        {"centroid": [50, 50, 50], "area": 2500},  # 大きな面
        {"centroid": [10, 10, 10], "area": 100},   # 中程度の面
        {"centroid": [5, 5, 5], "area": 25},       # 小さな面
        {"centroid": [0, 0, 0], "area": 0},        # デフォルトケース
    ]

    for i, face_data in enumerate(test_cases):
        print(f"\nケース{i+1}: 重心={face_data['centroid']}, 面積={face_data['area']}")
        boundaries = analyzer._generate_default_square_boundary(face_data)

        if boundaries and len(boundaries) > 0:
            boundary = boundaries[0]
            # 境界線のサイズを計算
            if len(boundary) >= 2:
                size = abs(boundary[1][0] - boundary[0][0])
                print(f"  生成された境界線サイズ: {size:.1f}mm")
        else:
            print("  境界線生成失敗")

    print("\n✓ 動的境界線生成テスト完了")


def test_projection_stability():
    """投影アルゴリズムの安定性テスト"""
    print("\n" + "=" * 60)
    print("テスト3: 投影アルゴリズムの安定性")
    print("=" * 60)

    import numpy as np
    engine = UnfoldEngine()

    # エッジケースのテスト
    test_cases = [
        {
            "name": "標準ケース",
            "normal": np.array([0, 0, 1]),
            "origin": np.array([0, 0, 0]),
            "points": [(10, 0, 5), (0, 10, 5), (-10, 0, 5), (0, -10, 5)]
        },
        {
            "name": "斜め法線",
            "normal": np.array([1, 1, 1]),
            "origin": np.array([10, 10, 10]),
            "points": [(20, 10, 10), (10, 20, 10), (10, 10, 20)]
        },
        {
            "name": "ほぼゼロ法線",
            "normal": np.array([0.001, 0.001, 0.001]),
            "origin": np.array([0, 0, 0]),
            "points": [(1, 1, 1), (2, 2, 2)]
        }
    ]

    for test_case in test_cases:
        print(f"\n{test_case['name']}:")
        print(f"  法線: {test_case['normal']}")

        try:
            projected = engine._project_points_to_plane_accurate(
                test_case['points'],
                test_case['normal'],
                test_case['origin'],
                numerical_tolerance=1e-6
            )
            print(f"  投影成功: {len(projected)}点")
            if len(projected) > 0:
                print(f"  最初の点: {projected[0]}")
        except Exception as e:
            print(f"  投影失敗: {e}")

    print("\n✓ 投影安定性テスト完了")


def test_face_grouping():
    """面グループ化の改善テスト"""
    print("\n" + "=" * 60)
    print("テスト4: 面グループ化の改善")
    print("=" * 60)

    engine = UnfoldEngine()

    # 仮想的な立方体の面データを作成
    faces_data = [
        {"unfoldable": True, "surface_type": "plane", "centroid": [50, 0, 0],
         "plane_normal": [1, 0, 0], "boundary_curves": [[(0,0,0), (1,0,0), (1,1,0), (0,1,0)]]},
        {"unfoldable": True, "surface_type": "plane", "centroid": [-50, 0, 0],
         "plane_normal": [-1, 0, 0], "boundary_curves": [[(0,0,0), (1,0,0), (1,1,0), (0,1,0)]]},
        {"unfoldable": True, "surface_type": "plane", "centroid": [0, 50, 0],
         "plane_normal": [0, 1, 0], "boundary_curves": [[(0,0,0), (1,0,0), (1,1,0), (0,1,0)]]},
        {"unfoldable": True, "surface_type": "plane", "centroid": [0, -50, 0],
         "plane_normal": [0, -1, 0], "boundary_curves": [[(0,0,0), (1,0,0), (1,1,0), (0,1,0)]]},
        {"unfoldable": True, "surface_type": "plane", "centroid": [0, 0, 50],
         "plane_normal": [0, 0, 1], "boundary_curves": [[(0,0,0), (1,0,0), (1,1,0), (0,1,0)]]},
        {"unfoldable": True, "surface_type": "plane", "centroid": [0, 0, -50],
         "plane_normal": [0, 0, -1], "boundary_curves": [[(0,0,0), (1,0,0), (1,1,0), (0,1,0)]]},
    ]

    edges_data = []  # 簡略化のため空

    engine.set_geometry_data(faces_data, edges_data)

    # グループ化有効でテスト
    print("\nグループ化有効:")
    groups = engine.group_faces_for_unfolding(max_faces=20, enable_grouping=True)
    print(f"生成されたグループ数: {len(groups)}")
    for i, group in enumerate(groups):
        print(f"  グループ{i}: 面{group}")

    # グループ化無効でテスト
    print("\nグループ化無効:")
    groups = engine.group_faces_for_unfolding(max_faces=20, enable_grouping=False)
    print(f"生成されたグループ数: {len(groups)}")

    print("\n✓ 面グループ化テスト完了")


def test_integration():
    """統合テスト：実際のBREPファイルで全体フローをテスト"""
    print("\n" + "=" * 60)
    print("テスト5: 統合テスト")
    print("=" * 60)

    try:
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox

        # テスト用の立方体を作成
        box = BRepPrimAPI_MakeBox(100, 100, 100).Shape()

        # テンポラリファイルに保存
        temp_file = tempfile.NamedTemporaryFile(suffix='.brep', delete=False)
        temp_file.close()

        from OCC.Core.BRepTools import BRepTools
        BRepTools.Write_s(box, temp_file.name)

        # StepUnfoldGeneratorで処理
        generator = StepUnfoldGenerator()

        # ファイル読み込み
        if generator.load_from_file(temp_file.name):
            print("✓ BREPファイル読み込み成功")

            # 解析
            generator.analyze_brep_topology()
            print(f"✓ トポロジ解析完了: {generator.stats['total_faces']}面検出")

            # グループ化
            groups = generator.group_faces_for_unfolding(max_faces=20)
            print(f"✓ 面グループ化完了: {len(groups)}グループ")

            # 展開
            unfolded = generator.unfold_face_groups()
            print(f"✓ 展開完了: {len(unfolded)}グループ展開")

            # 各グループの詳細
            for i, group in enumerate(unfolded):
                polygons = group.get('polygons', [])
                print(f"  グループ{i}: {len(polygons)}ポリゴン")
        else:
            print("✗ BREPファイル読み込み失敗")

        # クリーンアップ
        os.unlink(temp_file.name)

    except ImportError:
        print("OpenCASCADEが利用できないため、統合テストをスキップ")
    except Exception as e:
        print(f"統合テストエラー: {e}")
        import traceback
        traceback.print_exc()


def main():
    """全テストを実行"""
    print("\n" + "=" * 80)
    print(" 改善された展開アルゴリズムのテスト開始 ")
    print("=" * 80)

    # 各テストを実行
    test_boundary_simplification()
    test_dynamic_boundary_generation()
    test_projection_stability()
    test_face_grouping()
    test_integration()

    print("\n" + "=" * 80)
    print(" すべてのテスト完了 ")
    print("=" * 80)
    print("\n改善内容の概要:")
    print("1. Douglas-Peucker アルゴリズムによる形状保持簡略化")
    print("2. 面のスケールに応じた動的境界線生成")
    print("3. 数値安定性を向上させた投影アルゴリズム")
    print("4. 隣接面を考慮したインテリジェントなグループ化")
    print("5. 詳細なデバッグログによる問題の可視化")


if __name__ == "__main__":
    main()