#!/usr/bin/env python3
"""
エッジ共有ベースの隣接判定のテスト
Issue: 重心ベースの隣接判定が立方体で距離=0を返す問題を検証
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.unfold_engine import UnfoldEngine


def test_edge_sharing_detection():
    """エッジ共有ベースの隣接判定をテスト"""
    print("=" * 60)
    print("エッジ共有ベースの隣接判定テスト")
    print("=" * 60)

    engine = UnfoldEngine()

    # 立方体の6面をシミュレート
    # 面0: 上面 (z=1)
    # 面1: 下面 (z=0)
    # 面2: 前面 (y=1)
    # 面3: 背面 (y=0)
    # 面4: 右面 (x=1)
    # 面5: 左面 (x=0)

    faces_data = [
        {  # 面0: 上面
            "surface_type": "plane",
            "plane_normal": [0, 0, 1],
            "centroid": [0.5, 0.5, 1.0],
            "boundary_curves": [
                [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
            ]
        },
        {  # 面1: 下面
            "surface_type": "plane",
            "plane_normal": [0, 0, -1],
            "centroid": [0.5, 0.5, 0.0],
            "boundary_curves": [
                [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
            ]
        },
        {  # 面2: 前面
            "surface_type": "plane",
            "plane_normal": [0, 1, 0],
            "centroid": [0.5, 1.0, 0.5],
            "boundary_curves": [
                [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)]
            ]
        },
        {  # 面3: 背面
            "surface_type": "plane",
            "plane_normal": [0, -1, 0],
            "centroid": [0.5, 0.0, 0.5],
            "boundary_curves": [
                [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]
            ]
        },
        {  # 面4: 右面
            "surface_type": "plane",
            "plane_normal": [1, 0, 0],
            "centroid": [1.0, 0.5, 0.5],
            "boundary_curves": [
                [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]
            ]
        },
        {  # 面5: 左面
            "surface_type": "plane",
            "plane_normal": [-1, 0, 0],
            "centroid": [0.0, 0.5, 0.5],
            "boundary_curves": [
                [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)]
            ]
        },
    ]

    engine.set_geometry_data(faces_data, [])

    print("\n隣接関係のテスト:")
    print("-" * 60)

    # 期待される隣接関係をテスト
    test_cases = [
        (0, 2, True, "上面と前面は隣接（エッジ共有）"),
        (0, 3, True, "上面と背面は隣接（エッジ共有）"),
        (0, 4, True, "上面と右面は隣接（エッジ共有）"),
        (0, 5, True, "上面と左面は隣接（エッジ共有）"),
        (0, 1, False, "上面と下面は隣接しない（反対側）"),
        (2, 3, False, "前面と背面は隣接しない（反対側）"),
        (4, 5, False, "右面と左面は隣接しない（反対側）"),
        (1, 2, True, "下面と前面は隣接（エッジ共有）"),
    ]

    passed = 0
    failed = 0

    for face1, face2, expected, description in test_cases:
        result = engine._are_faces_adjacent(face1, face2)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} 面{face1} <-> 面{face2}: {result} (期待: {expected}) - {description}")

    print("\n" + "=" * 60)
    print(f"結果: {passed}成功 / {failed}失敗")
    print("=" * 60)

    if failed > 0:
        print("⚠ 一部のテストが失敗しました")
        return False
    else:
        print("✓ すべてのテストが成功しました")
        return True


def test_grouping_with_edge_detection():
    """エッジ検出を使ったグループ化のテスト"""
    print("\n" + "=" * 60)
    print("グループ化テスト（エッジ検出使用）")
    print("=" * 60)

    engine = UnfoldEngine()

    # 同じ立方体データを使用
    faces_data = [
        {"surface_type": "plane", "plane_normal": [0, 0, 1], "centroid": [0.5, 0.5, 1.0], "unfoldable": True,
         "boundary_curves": [[(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]]},
        {"surface_type": "plane", "plane_normal": [0, 0, -1], "centroid": [0.5, 0.5, 0.0], "unfoldable": True,
         "boundary_curves": [[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]]},
        {"surface_type": "plane", "plane_normal": [0, 1, 0], "centroid": [0.5, 1.0, 0.5], "unfoldable": True,
         "boundary_curves": [[(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)]]},
        {"surface_type": "plane", "plane_normal": [0, -1, 0], "centroid": [0.5, 0.0, 0.5], "unfoldable": True,
         "boundary_curves": [[(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]]},
        {"surface_type": "plane", "plane_normal": [1, 0, 0], "centroid": [1.0, 0.5, 0.5], "unfoldable": True,
         "boundary_curves": [[(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]]},
        {"surface_type": "plane", "plane_normal": [-1, 0, 0], "centroid": [0.0, 0.5, 0.5], "unfoldable": True,
         "boundary_curves": [[(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)]]},
    ]

    edges_data = []  # 空でも動作するはず

    engine.set_geometry_data(faces_data, edges_data)

    print("\nグループ化実行中...")
    groups = engine.group_faces_for_unfolding(max_faces=100, enable_grouping=True)

    print(f"\n生成されたグループ数: {len(groups)}")
    for i, group in enumerate(groups):
        print(f"  グループ{i}: 面{group} ({len(group)}面)")

    # 立方体の場合、各面が90度で交わるため、同一平面のグループはない
    # したがって、6つの個別グループになるはず
    print(f"\n期待: 6グループ（各面が個別）")
    print(f"実際: {len(groups)}グループ")

    if len(groups) == 6:
        print("✓ グループ化は正しく動作しています")
        return True
    else:
        print("⚠ グループ化が期待通りではありません")
        return False


def main():
    """全テストを実行"""
    print("\n" + "=" * 80)
    print(" エッジ共有ベースの隣接判定 - 修正版テスト ")
    print("=" * 80)

    test1_passed = test_edge_sharing_detection()
    test2_passed = test_grouping_with_edge_detection()

    print("\n" + "=" * 80)
    if test1_passed and test2_passed:
        print("✅ すべてのテストが成功しました")
        print("=" * 80)
        print("\n修正内容:")
        print("1. 重心ベースの隣接判定 → エッジ共有ベースの隣接判定")
        print("2. 共有頂点を検出（2つ以上でエッジ共有とみなす）")
        print("3. 同一平面の面のみをグループ化（角度閾値 ~18度）")
        return 0
    else:
        print("❌ 一部のテストが失敗しました")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
