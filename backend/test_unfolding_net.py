#!/usr/bin/env python3
"""
展開ネット生成モードのテストスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.unfold_engine import UnfoldEngine


def test_unfolding_net_mode():
    """展開ネット生成モードのテスト"""
    print("=" * 60)
    print("展開ネット生成モードのテスト")
    print("=" * 60)

    engine = UnfoldEngine()

    # 立方体の6面をシミュレート
    faces_data = [
        {  # 面0: 上面
            "surface_type": "plane",
            "plane_normal": [0, 0, 1],
            "plane_origin": [0, 0, 1],
            "centroid": [0.5, 0.5, 1.0],
            "unfoldable": True,
            "face_number": 1,
            "boundary_curves": [
                [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
            ]
        },
        {  # 面1: 下面
            "surface_type": "plane",
            "plane_normal": [0, 0, -1],
            "plane_origin": [0, 0, 0],
            "centroid": [0.5, 0.5, 0.0],
            "unfoldable": True,
            "face_number": 2,
            "boundary_curves": [
                [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
            ]
        },
        {  # 面2: 前面
            "surface_type": "plane",
            "plane_normal": [0, 1, 0],
            "plane_origin": [0, 1, 0],
            "centroid": [0.5, 1.0, 0.5],
            "unfoldable": True,
            "face_number": 3,
            "boundary_curves": [
                [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)]
            ]
        },
        {  # 面3: 背面
            "surface_type": "plane",
            "plane_normal": [0, -1, 0],
            "plane_origin": [0, 0, 0],
            "centroid": [0.5, 0.0, 0.5],
            "unfoldable": True,
            "face_number": 4,
            "boundary_curves": [
                [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]
            ]
        },
        {  # 面4: 右面
            "surface_type": "plane",
            "plane_normal": [1, 0, 0],
            "plane_origin": [1, 0, 0],
            "centroid": [1.0, 0.5, 0.5],
            "unfoldable": True,
            "face_number": 5,
            "boundary_curves": [
                [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]
            ]
        },
        {  # 面5: 左面
            "surface_type": "plane",
            "plane_normal": [-1, 0, 0],
            "plane_origin": [0, 0, 0],
            "centroid": [0.0, 0.5, 0.5],
            "unfoldable": True,
            "face_number": 6,
            "boundary_curves": [
                [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)]
            ]
        },
    ]

    edges_data = []

    engine.set_geometry_data(faces_data, edges_data)

    print("\nテスト1: 通常のグループ化（同一平面のみ）")
    print("-" * 60)
    groups = engine.group_faces_for_unfolding(max_faces=100, enable_grouping=True, generate_unfolding_net=False)
    print(f"グループ数: {len(groups)}")
    print(f"期待: 6グループ（立方体の各面が個別）")
    print(f"結果: {'✓ 正常' if len(groups) == 6 else '✗ 異常'}")

    print("\nテスト2: 展開ネット生成モード")
    print("-" * 60)
    groups = engine.group_faces_for_unfolding(max_faces=100, enable_grouping=True, generate_unfolding_net=True)
    print(f"グループ数: {len(groups)}")
    print(f"期待: 1グループ（すべての面を展開ネットとして生成）")
    print(f"結果: {'✓ 正常' if len(groups) == 1 and len(groups[0]) == 6 else '✗ 異常'}")

    if len(groups) == 1 and len(groups[0]) == 6:
        print(f"グループ0の面数: {len(groups[0])}")
        print(f"グループ0の面インデックス: {groups[0]}")

        # 展開を実行
        print("\n展開ネットを生成中...")
        unfolded = engine.unfold_face_groups()
        print(f"展開されたグループ数: {len(unfolded)}")

        if len(unfolded) > 0:
            group = unfolded[0]
            print(f"  グループ0:")
            print(f"    ポリゴン数: {len(group.get('polygons', []))}")
            print(f"    面番号: {group.get('face_numbers', [])}")
            print(f"    面インデックス: {group.get('face_indices', [])}")

    print("\n" + "=" * 60)
    print("テスト完了")
    print("=" * 60)


if __name__ == "__main__":
    test_unfolding_net_mode()
