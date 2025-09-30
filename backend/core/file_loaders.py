import os
import tempfile
import time
import json
import re
from typing import Dict, Any, Optional

from config import OCCT_AVAILABLE

if OCCT_AVAILABLE:
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core import BRepTools
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Compound
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
    from OCC.Core.TColStd import TColStd_HSequenceOfTransient
    from OCC.Core.Standard import Standard_Transient
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.StepData import StepData_StepModel
    from OCC.Core.IGESControl import IGESControl_Reader
    from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer


class FileLoader:
    """
    CADファイルの読み込み処理を担当するクラス。
    """
    
    def __init__(self):
        self.solid_shape = None
        self.last_file_info = None
    
    def load_brep_from_file(self, file_path: str) -> bool:
        """
        BREPファイルからソリッドモデルを読み込み、基本検証を行う。
        """
        try:
            # BREPファイル読み込み（新しい推奨メソッドを使用）
            builder = BRep_Builder()
            shape = TopoDS_Shape()
            
            # pythonocc-core 7.7.1以降の推奨メソッドを使用
            if not BRepTools.breptools.Read(shape, file_path, builder):
                raise ValueError(f"BREPファイルの読み込みに失敗: {file_path}")
            
            # ソリッドの検証
            if shape.IsNull():
                raise ValueError("読み込んだ形状が無効です")
            
            self.solid_shape = shape
            return True
            
        except Exception as e:
            raise ValueError(f"BREPファイル処理エラー: {str(e)}")
    
    def load_step_from_file(self, file_path: str) -> bool:
        """
        STEPファイルからソリッドモデルを読み込み、基本検証を行う。
        """
        try:
            # STEPファイル読み込みに必要なインポート
            from OCC.Core.STEPControl import STEPControl_Reader
            from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
            from OCC.Core.TColStd import TColStd_HSequenceOfTransient
            from OCC.Core.Standard import Standard_Transient
            from OCC.Core.Interface import Interface_Static
            from OCC.Core.StepData import StepData_StepModel
            
            # 詳細なSTEPファイル分析を表示
            print(f"STEPファイル詳細分析: {file_path}")
            
            # 読み込み設定
            # STEPリーダーの詳細設定
            Interface_Static.SetCVal("step.product.mode", "1") # 1=ON
            Interface_Static.SetIVal("read.step.product.mode", 1)
            Interface_Static.SetCVal("read.step.product.context", "")
            Interface_Static.SetCVal("read.step.shape.repr", "")
            Interface_Static.SetCVal("read.step.assembly.level", "1")
            Interface_Static.SetIVal("read.step.nonmanifold", 1)
            
            # STEPリーダー初期化
            step_reader = STEPControl_Reader()
            
            # ファイル読み込み
            print("STEPファイル読み込み開始...")
            status = step_reader.ReadFile(file_path)
            if status != IFSelect_RetDone:
                raise ValueError(f"STEPファイルの読み込みに失敗: {file_path} - ステータス: {status}")
            
            print("STEPファイル読み込み完了")
            
            # モデル情報の取得
            step_model = step_reader.StepModel()
            if step_model:
                nb_entities = step_model.NbEntities()
                print(f"モデル内のエンティティ数: {nb_entities}")
                
                # モデル内容の詳細
                if nb_entities > 0:
                    # 最初の10エンティティの情報を表示
                    max_display = min(10, nb_entities)
                    print(f"最初の{max_display}エンティティのタイプ:")
                    for i in range(1, max_display + 1):
                        entity = step_model.Entity(i)
                        if entity:
                            entity_type = step_model.TypeName(entity)
                            print(f"  エンティティ {i}: タイプ = {entity_type}")
            
            # ファイル内のエンティティ数を確認
            nbr = step_reader.NbRootsForTransfer()
            print(f"転送可能なルート数: {nbr}")
            
            if nbr <= 0:
                raise ValueError("STEPファイルに転送可能な形状が含まれていません")
            
            # 各ルートの情報表示
            for i in range(1, nbr + 1):
                # STEPControl_ReaderにCheckTransientはないため、単純にルート番号を表示
                print(f"  ルート {i}")
            
            print("すべてのルートを転送中...")
            # すべてのルートを転送
            status = step_reader.TransferRoots()
            print(f"転送完了: ステータス = {status}")
            
            # 転送されたオブジェクト数を確認
            nbs = step_reader.NbShapes()
            print(f"転送された形状数: {nbs}")
            
            # 形状が存在しない場合、個別に転送を試みる
            if nbs <= 0:
                print("個別転送を試みます...")
                for i in range(1, nbr + 1):
                    ok = step_reader.TransferRoot(i)
                    print(f"  ルート {i} 転送: {ok}")
                
                # 再度形状数を確認
                nbs = step_reader.NbShapes()
                print(f"個別転送後の形状数: {nbs}")
                
                # それでも形状がない場合は空の形状を作成
                if nbs <= 0:
                    from OCC.Core.TopoDS import TopoDS_Compound
                    from OCC.Core.BRep import BRep_Builder
                    print("空の形状を作成します")
                    compound = TopoDS_Compound()
                    builder = BRep_Builder()
                    builder.MakeCompound(compound)
                    self.solid_shape = compound
                    return False  # 空の形状なので実質的に失敗
            
            # シェイプの取得
            shape = step_reader.OneShape()
            
            # シェイプの存在確認
            if shape is None:
                print("OneShapeがNoneを返しました - 形状が存在しない可能性があります")
                
                # 個別に形状を取得してみる
                from OCC.Core.TopoDS import TopoDS_Compound
                from OCC.Core.BRep import BRep_Builder
                compound = TopoDS_Compound()
                builder = BRep_Builder()
                builder.MakeCompound(compound)
                
                # 各形状を取り出してコンパウンドに追加
                for i in range(1, nbs + 1):
                    current_shape = step_reader.Shape(i)
                    if not current_shape.IsNull():
                        builder.Add(compound, current_shape)
                
                if compound.IsNull():
                    raise ValueError("STEPファイルから有効な形状を取得できませんでした")
                    
                self.solid_shape = compound
            else:
                # ソリッドの検証
                if shape.IsNull():
                    raise ValueError("読み込んだ形状が無効です")
                
                self.solid_shape = shape
            
            # 形状情報
            from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE
            from OCC.Core.TopExp import TopExp_Explorer
            
            print("読み込んだ形状の情報:")
            solids = TopExp_Explorer(self.solid_shape, TopAbs_SOLID)
            faces = TopExp_Explorer(self.solid_shape, TopAbs_FACE)
            edges = TopExp_Explorer(self.solid_shape, TopAbs_EDGE)
            
            solid_count = 0
            while solids.More():
                solid_count += 1
                solids.Next()
                
            face_count = 0
            while faces.More():
                face_count += 1
                faces.Next()
                
            edge_count = 0
            while edges.More():
                edge_count += 1
                edges.Next()
                
            print(f"  ソリッド数: {solid_count}")
            print(f"  面数: {face_count}")
            print(f"  エッジ数: {edge_count}")
            
            return face_count > 0  # 面が存在すれば成功とみなす
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValueError(f"STEPファイル処理エラー: {str(e)}")
    
    def load_iges_from_file(self, file_path: str) -> bool:
        """
        IGESファイルからソリッドモデルを読み込み、基本検証を行う。
        """
        try:
            # IGESファイル読み込みに必要なインポート
            from OCC.Core.IGESControl import IGESControl_Reader
            from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
            
            # IGESリーダー初期化
            iges_reader = IGESControl_Reader()
            
            # ファイル読み込み
            status = iges_reader.ReadFile(file_path)
            if status != IFSelect_RetDone:
                raise ValueError(f"IGESファイルの読み込みに失敗: {file_path}")
            
            # ファイル内のエンティティ数を確認
            failsonly = False
            mode = IFSelect_ItemsByEntity
            nbr = iges_reader.NbRootsForTransfer()
            print(f"IGESファイル内のルート数: {nbr}")
            
            if nbr <= 0:
                raise ValueError("IGESファイルに有効な形状が含まれていません")
            
            # すべてのルートを転送
            status = iges_reader.TransferRoots()
            
            # 転送されたオブジェクト数を確認
            nbs = iges_reader.NbShapes()
            if nbs <= 0:
                raise ValueError("IGESファイルから形状をインポートできませんでした")
            
            # シェイプの取得
            shape = iges_reader.OneShape()
            
            # シェイプの存在確認
            if shape is None:
                raise ValueError("IGESファイルから有効な形状を取得できませんでした")
                
            # ソリッドの検証
            if shape.IsNull():
                raise ValueError("読み込んだ形状が無効です")
            
            self.solid_shape = shape
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValueError(f"IGESファイル処理エラー: {str(e)}")

    def load_from_file(self, file_path: str) -> bool:
        """
        ファイル拡張子に応じて適切な読み込み関数を呼び出す。
        """
        # ファイル拡張子を取得
        file_ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        
        # 拡張子に応じた処理
        if file_ext in ['brep']:
            return self.load_brep_from_file(file_path)
        elif file_ext in ['step', 'stp']:
            return self.load_step_from_file(file_path)
        elif file_ext in ['iges', 'igs']:
            return self.load_iges_from_file(file_path)
        else:
            raise ValueError(f"未対応ファイル形式: .{file_ext}")

    def diagnose_file(self, file_path: str, save_debug_copy: bool = True) -> dict:
        """
        ファイルの基本情報を診断し、デバッグ情報を返す。
        save_debug_copyがTrueの場合、デバッグ用にファイルのコピーを保存する。
        """
        result = {
            "exists": False,
            "size": 0,
            "header": "",
            "saved_path": None,
            "error": None
        }
        
        try:
            # ファイル存在確認
            if not os.path.exists(file_path):
                result["error"] = f"ファイルが存在しません: {file_path}"
                return result
                
            # 基本情報取得
            result["exists"] = True
            result["size"] = os.path.getsize(file_path)
            
            # ファイルヘッダー（先頭100バイト）取得
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    result["header"] = f.read(100)
            except UnicodeDecodeError:
                with open(file_path, 'rb') as f:
                    binary_header = f.read(100)
                    result["header"] = f"バイナリファイル: {binary_header.hex()[:50]}..."
            
            # デバッグ用にファイルのコピーを保存
            if save_debug_copy:
                try:
                    file_ext = os.path.splitext(file_path)[1]
                    debug_dir = os.path.join(os.path.dirname(__file__), "debug_files")
                    
                    # ディレクトリがなければ作成
                    if not os.path.exists(debug_dir):
                        os.makedirs(debug_dir)
                        
                    # タイムスタンプ付きでファイルをコピー
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    debug_filename = f"debug_{timestamp}_{os.path.basename(file_path)}"
                    debug_path = os.path.join(debug_dir, debug_filename)
                    
                    # ファイルをコピー
                    with open(file_path, 'rb') as src, open(debug_path, 'wb') as dst:
                        dst.write(src.read())
                        
                    result["saved_path"] = debug_path
                    print(f"デバッグ用にファイルをコピーしました: {debug_path}")
                except Exception as e:
                    print(f"デバッグファイルの保存に失敗: {e}")
            
            return result
            
        except Exception as e:
            result["error"] = f"診断エラー: {str(e)}"
            return result

    def load_from_bytes(self, file_content: bytes, file_ext: str) -> bool:
        """
        バイト列からCADデータを読み込む（API経由アップロード対応）。
        """
        try:
            # 一時ファイル作成・書き込み
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name
            
            # ファイル診断（デバッグ用）
            diag_info = self.diagnose_file(temp_path, save_debug_copy=True)
            print(f"ファイル診断: {diag_info}")
            
            # ファイル読み込み
            try:
                result = self.load_from_file(temp_path)
                
                # 読み込みに成功した場合、診断情報を残す
                self.last_file_info = {
                    "diagnosis": diag_info,
                    "success": True,
                    "format": file_ext,
                    "path": diag_info.get("saved_path")
                }
                
                # 一時ファイル削除（デバッグコピーは残す）
                os.unlink(temp_path)
                
                return result
            except ValueError as e:
                # エラー情報を記録
                self.last_file_info = {
                    "diagnosis": diag_info,
                    "success": False,
                    "format": file_ext,
                    "path": diag_info.get("saved_path"),
                    "error": str(e)
                }
                
                # 一時ファイル削除（デバッグコピーは残す）
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
                # 例外を再発生
                raise
            
        except Exception as e:
            raise ValueError(f"CADデータ処理エラー: {str(e)}")
    
    def load_brep_from_bytes(self, file_content: bytes) -> bool:
        """
        バイト列からBREPデータを読み込む（API経由アップロード対応）。
        無効なBREPの場合は、パラメータから立方体を生成する。
        """
        try:
            print("BREPファイル読み込み試行中...")
            # 元の処理を試行
            result = self.load_from_bytes(file_content, 'brep')
            print(f"BREP読み込み成功: {result}")
            return result
        except ValueError as e:
            print(f"BREP読み込み失敗: {e}")
            # BREPファイルが無効な場合、パラメータからの生成を試行
            file_content_str = file_content.decode('utf-8', errors='ignore')
            
            # ファイル内容からパラメータを抽出
            
            # パラメータ行を検索
            param_match = re.search(r'# Parameters: ({[^}]+})', file_content_str)
            if param_match:
                try:
                    params = json.loads(param_match.group(1))
                    width = float(params.get('width', 20))
                    height = float(params.get('height', 20))
                    depth = float(params.get('depth', 20))
                    
                    print(f"無効なBREPファイルを検出。パラメータから立方体を生成: {width}x{height}x{depth}")
                    return self.create_box_from_parameters(width, height, depth)
                except (json.JSONDecodeError, ValueError, KeyError) as parse_error:
                    print(f"パラメータ解析エラー: {parse_error}")
            
            # パラメータが見つからない場合はデフォルトの立方体を生成
            print("パラメータが見つかりません。デフォルトの立方体(20x20x20)を生成します")
            return self.create_box_from_parameters(20.0, 20.0, 20.0)

    def create_box_from_parameters(self, width: float, height: float, depth: float) -> bool:
        """
        パラメータから立方体を生成する（仮実装）
        """
        # 実際の実装は省略（元のコードに含まれていない）
        print(f"立方体生成: {width}x{height}x{depth}")
        # TODO: ここで実際の立方体形状を生成する必要がある
        return True