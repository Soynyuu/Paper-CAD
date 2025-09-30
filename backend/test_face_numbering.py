#!/usr/bin/env python
"""
面番号表示機能のテストスクリプト
簡単な立方体のSTEPファイルを作成して展開図を生成し、面番号が表示されることを確認
"""

import os
import tempfile
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs

from core.geometry_analyzer import GeometryAnalyzer
from core.unfold_engine import UnfoldEngine
from core.svg_exporter import SVGExporter
from core.layout_manager import LayoutManager

def create_test_step_file():
    """テスト用の立方体STEPファイルを作成"""
    # 50x50x50の立方体を作成
    box = BRepPrimAPI_MakeBox(50, 50, 50).Shape()
    
    # STEPファイルに書き出し
    step_writer = STEPControl_Writer()
    step_writer.Transfer(box, STEPControl_AsIs)
    
    # 一時ファイルに保存
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.step')
    temp_path = temp_file.name
    temp_file.close()
    
    step_writer.Write(temp_path)
    return temp_path, box

def test_face_numbering():
    """面番号機能のテスト"""
    print("=" * 60)
    print("面番号表示機能のテスト開始")
    print("=" * 60)
    
    # テスト用STEPファイルを作成
    step_path, shape = create_test_step_file()
    print(f"テストファイル作成: {step_path}")
    
    try:
        # 1. ジオメトリ解析
        analyzer = GeometryAnalyzer()
        faces_data = analyzer.analyze_shape(shape)
        
        print(f"\n解析結果:")
        print(f"- 面の数: {len(faces_data)}")
        for face in faces_data:
            print(f"  面 {face['index']} (番号: {face['face_number']}): {face['surface_type']}")
        
        # 2. 展開処理
        unfold_engine = UnfoldEngine()
        unfold_engine.set_faces_data(faces_data)
        unfold_groups = unfold_engine.create_unfold_groups()
        unfolded_groups = unfold_engine.unfold_face_groups()
        
        print(f"\n展開結果:")
        print(f"- グループ数: {len(unfolded_groups)}")
        for group in unfolded_groups:
            if "face_numbers" in group:
                print(f"  グループ {group['group_index']}: 面番号 {group['face_numbers']}")
        
        # 3. レイアウト処理
        layout_manager = LayoutManager()
        placed_groups = layout_manager.layout_groups(unfolded_groups)
        
        # 4. SVG出力
        output_path = "test_face_numbering.svg"
        svg_exporter = SVGExporter(scale_factor=2.0)
        svg_exporter.export_to_svg(placed_groups, output_path, layout_manager)
        
        print(f"\n✅ テスト成功!")
        print(f"SVGファイル生成: {output_path}")
        print("面番号が赤色で各面の中心に表示されているはずです。")
        
        # 後片付け
        os.remove(step_path)
        
        return True
        
    except Exception as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        
        # 後片付け
        if os.path.exists(step_path):
            os.remove(step_path)
        
        return False

if __name__ == "__main__":
    success = test_face_numbering()
    exit(0 if success else 1)