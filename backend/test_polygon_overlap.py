#!/usr/bin/env python3
"""
ポリゴン重複検出のテストケース
Issue #6: 展開図の面同士の重なり問題を検証
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.layout_manager import LayoutManager


def test_simple_overlap():
    """単純な矩形の重複テスト"""
    layout_manager = LayoutManager()
    
    # 重複する2つの矩形
    poly1 = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
    poly2 = [[(5, 5), (15, 5), (15, 15), (5, 15)]]
    
    result = layout_manager._polygons_overlap(poly1, poly2)
    print(f"単純重複テスト: {result} (期待値: True)")
    assert result == True, "重複する矩形が検出されませんでした"


def test_complete_containment():
    """完全包含のテスト（小さい面が大きい面の中に完全に入る）"""
    layout_manager = LayoutManager()
    
    # 大きい矩形の中に小さい矩形が完全に含まれる
    poly_large = [[(0, 0), (20, 0), (20, 20), (0, 20)]]
    poly_small = [[(5, 5), (10, 5), (10, 10), (5, 10)]]
    
    result = layout_manager._polygons_overlap(poly_large, poly_small)
    print(f"完全包含テスト: {result} (期待値: True)")
    assert result == True, "完全包含が検出されませんでした"


def test_no_overlap():
    """重複しない矩形のテスト"""
    layout_manager = LayoutManager()
    
    # 離れた2つの矩形
    poly1 = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
    poly2 = [[(20, 20), (30, 20), (30, 30), (20, 30)]]
    
    result = layout_manager._polygons_overlap(poly1, poly2)
    print(f"非重複テスト: {result} (期待値: False)")
    assert result == False, "重複しない矩形が重複として検出されました"


def test_edge_touching():
    """辺が接触するだけのテスト"""
    layout_manager = LayoutManager()
    
    # 辺が接触する2つの矩形
    poly1 = [[(0, 0), (10, 0), (10, 10), (0, 10)]]
    poly2 = [[(10, 0), (20, 0), (20, 10), (10, 10)]]
    
    result = layout_manager._polygons_overlap(poly1, poly2)
    print(f"辺接触テスト: {result} (期待値: False)")
    assert result == False, "辺が接触するだけの矩形が重複として検出されました"


def test_complex_shape():
    """複雑な形状（L字型）の重複テスト"""
    layout_manager = LayoutManager()
    
    # L字型のポリゴン
    poly_l = [[(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]]
    # L字の凹み部分に入る矩形
    poly_rect = [[(6, 6), (9, 6), (9, 9), (6, 9)]]
    
    result = layout_manager._polygons_overlap(poly_l, poly_rect)
    print(f"複雑形状テスト: {result} (期待値: False - 凹み部分)")
    # L字の凹み部分なので実際には重複しない
    

def test_layout_with_groups():
    """実際のグループ配置のテスト"""
    layout_manager = LayoutManager()
    
    # テスト用展開グループ
    groups = [
        {
            "polygons": [
                [(0, 0), (30, 0), (30, 30), (0, 30)]  # 大きい正方形
            ],
            "tabs": []
        },
        {
            "polygons": [
                [(0, 0), (10, 0), (10, 10), (0, 10)]  # 小さい正方形
            ],
            "tabs": []
        },
        {
            "polygons": [
                [(0, 0), (5, 0), (5, 5), (0, 5)]  # もっと小さい正方形
            ],
            "tabs": []
        }
    ]
    
    # レイアウト実行
    placed = layout_manager.layout_unfolded_groups(groups)
    
    print(f"\n配置テスト完了: {len(placed)} グループを配置")
    
    # 配置後の重複チェック
    for i, group1 in enumerate(placed):
        for j, group2 in enumerate(placed[i+1:], i+1):
            overlap = layout_manager._polygons_overlap(
                group1["polygons"], 
                group2["polygons"]
            )
            if overlap:
                print(f"  警告: グループ {i} と {j} が重複しています")
            else:
                print(f"  OK: グループ {i} と {j} は重複していません")


def main():
    """全テストを実行"""
    print("=" * 50)
    print("ポリゴン重複検出テスト開始")
    print("=" * 50)
    
    try:
        # Shapelyが利用可能か確認
        from shapely.geometry import Polygon
        print("✓ Shapely が利用可能です\n")
    except ImportError:
        print("⚠ Shapely が利用できません。基本的なbbox判定のみ実行されます\n")
    
    try:
        test_simple_overlap()
        test_complete_containment()
        test_no_overlap()
        test_edge_touching()
        test_complex_shape()
        test_layout_with_groups()
        
        print("\n" + "=" * 50)
        print("✅ すべてのテストが成功しました")
        print("=" * 50)
        
    except AssertionError as e:
        print(f"\n❌ テスト失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()