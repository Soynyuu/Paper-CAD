import os
import tempfile
import uuid
import zipfile
from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from typing import Optional
import io

from config import OCCT_AVAILABLE
from services.step_processor import StepUnfoldGenerator
from models.request_models import BrepPapercraftRequest
from services.citygml_to_step import export_step_from_citygml, parse_citygml_footprints

# APIルーターの作成
router = APIRouter()

# --- STEP専用APIエンドポイント ---
@router.post("/api/step/unfold")
async def unfold_step_to_svg(
    file: UploadFile = File(...),
    return_face_numbers: bool = Form(True),
    output_format: str = Form("svg"),
    layout_mode: str = Form("canvas"),
    page_format: str = Form("A4"),
    page_orientation: str = Form("portrait"),
    scale_factor: float = Form(10.0),
    texture_mappings: Optional[str] = Form(None)
):
    """
    STEPファイル（.step/.stp）を受け取り、展開図（SVG）を生成するAPI。

    Args:
        file: STEPファイル (.step/.stp)
        return_face_numbers: 面番号データを含むかどうか (default: True)
        output_format: 出力形式 - "svg"=SVGファイル、"json"=JSONレスポンス
        layout_mode: レイアウトモード - "canvas"=フリーキャンバス、"paged"=ページ分割 (default: "canvas")
        page_format: ページフォーマット - "A4", "A3", "Letter" (default: "A4")
        page_orientation: ページ方向 - "portrait"=縦、"landscape"=横 (default: "portrait")
        scale_factor: 図の縮尺倍率 (default: 10.0) - 例: 150なら1/150スケール
        texture_mappings: JSON形式のテクスチャマッピング情報 - [{faceNumber, patternId, tileCount}]

    Returns:
        - output_format="svg": 単一SVGファイル（pagedモードでは全ページを縦に並べて表示）
        - output_format="json": JSONレスポンス
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。")
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
            raise HTTPException(status_code=400, detail="STEPファイル（.step/.stp）のみ対応です。")

        # 大容量でも安定するようチャンクで一時保存
        tmpdir = tempfile.mkdtemp()
        file_ext = "step" if file.filename.lower().endswith('.step') else "stp"
        in_path = os.path.join(tmpdir, f"{uuid.uuid4()}.{file_ext}")
        total = 0
        with open(in_path, "wb") as dst:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                total += len(chunk)
                dst.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="アップロードされたファイルが空です。")
        print(f"[UPLOAD] /api/step/unfold: received {total} bytes -> {in_path}")

        # テクスチャマッピングのパース
        parsed_texture_mappings = []
        if texture_mappings:
            try:
                import json
                parsed_texture_mappings = json.loads(texture_mappings)
                print(f"[TEXTURE] Received texture mappings: {parsed_texture_mappings}")
            except json.JSONDecodeError as e:
                print(f"[TEXTURE] Failed to parse texture mappings: {e}")
                # エラーを無視してテクスチャなしで続行

        # StepUnfoldGeneratorインスタンスを作成
        step_unfold_generator = StepUnfoldGenerator()

        # 一時保存したファイルからロード
        if not step_unfold_generator.load_from_file(in_path):
            raise HTTPException(status_code=400, detail="STEPファイルの読み込みに失敗しました。")
        output_path = os.path.join(tempfile.mkdtemp(), f"step_unfold_{uuid.uuid4()}.svg")

        # レイアウトオプションを含むBrepPapercraftRequestを作成
        request = BrepPapercraftRequest(
            layout_mode=layout_mode,
            page_format=page_format,
            page_orientation=page_orientation,
            scale_factor=scale_factor
        )

        # テクスチャマッピングを渡す
        if parsed_texture_mappings:
            step_unfold_generator.set_texture_mappings(parsed_texture_mappings)

        svg_path, stats = step_unfold_generator.generate_brep_papercraft(request, output_path)
        
        # 出力形式に応じてレスポンスを分岐
        if output_format.lower() == "json":
            # JSONレスポンス形式
            with open(svg_path, 'r', encoding='utf-8') as svg_file:
                svg_content = svg_file.read()
            
            response_data = {
                "svg_content": svg_content,
                "stats": stats
            }
            
            try:
                os.unlink(svg_path)
            except:
                pass
            
            # 面番号データを含める場合
            if return_face_numbers:
                face_numbers = step_unfold_generator.get_face_numbers()
                response_data["face_numbers"] = face_numbers
            
            return response_data
        else:
            # SVGファイルレスポンス
            # ページモードでも単一ファイルに全ページが含まれる
            return FileResponse(
                path=svg_path,
                media_type="image/svg+xml",
                filename=f"step_unfold_{layout_mode}_{uuid.uuid4()}.svg",
                headers={
                    "X-Layout-Mode": layout_mode,
                    "X-Page-Format": page_format if layout_mode == "paged" else "N/A",
                    "X-Page-Orientation": page_orientation if layout_mode == "paged" else "N/A",
                    "X-Page-Count": str(stats.get("page_count", 1)) if layout_mode == "paged" else "1"
                }
            )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")

# --- CityGML → STEP 変換エンドポイント ---
@router.post(
    "/api/citygml/to-step",
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
            "description": "STEP file generated successfully"
        }
    },
    response_class=FileResponse,
)
async def citygml_to_step(
    request: Request,
    file: Optional[UploadFile] = File(
        None,
        description="CityGMLファイル（.gml/.xml）をアップロード（file か gml_path のどちらかを指定）",
    ),
    gml_path: Optional[str] = Form(
        None,
        description="サーバーローカルのCityGMLの絶対パス",
        example="/abs/path/to/53394642_bldg_6697_op.gml",
    ),
    default_height: float = Form(10.0, description="押し出し時のデフォルト高さ（m）"),
    limit: Optional[int] = Form(
        5,
        description="処理する建物数の上限（未指定で5、0/負数で無制限）",
        example=10,
    ),
    debug: bool = Form(False, description="デバッグログ出力を有効化"),
    method: str = Form(
        "auto",
        description="変換方式：auto（Solid→縫合→押し出し）, solid（LOD1/2直接）, sew（縫合）, extrude（押し出し）",
    ),
    sew_tolerance: float = Form(1e-6, description="LOD2サーフェス縫合トレランス（m）", example=0.001),
    reproject_to: Optional[str] = Form(
        None,
        description="出力の平面直角/投影座標系（例: EPSG:6676）。未指定で自動選択",
        example="EPSG:6676",
    ),
    source_crs: Optional[str] = Form(
        None,
        description="入力の座標系を明示（例: EPSG:6697）。未指定ならGMLのsrsNameから推定",
        example="EPSG:6697",
    ),
    auto_reproject: bool = Form(
        True,
        description="地理座標系を検出した場合、自動的に適切な投影座標系に変換",
    ),
):
    """
    CityGML (.gml) を受け取り、押し出しヒューリスティックで STEP を生成します。

    - 入力はアップロードファイルまたはローカルパス (gml_path) のどちらかを指定
    - フットプリント＋高さを推定し、OCCT で押し出し、STEP(AP214)を書き出し
    - 地理座標系（緯度経度）を検出した場合、自動的に適切な平面直角座標系に変換
    - 日本のPLATEAUデータの場合、地域に応じた日本平面直角座標系を自動選択
    """
    try:
        if file is None and not gml_path:
            raise HTTPException(status_code=400, detail="CityGMLファイルをアップロードするか gml_path を指定してください。")

        # 入力ファイルの用意
        if file is not None:
            if not file.filename.lower().endswith((".gml", ".xml")):
                raise HTTPException(status_code=400, detail="CityGML (.gml/.xml) に対応しています。")
            
            # ファイルサイズチェック（100MB制限）
            if hasattr(file, 'size') and file.size and file.size > 100 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="ファイルサイズが大きすぎます（最大100MB）。より小さいファイルを使用するか、limitパラメータで処理する建物数を制限してください。"
                )
            tmpdir = tempfile.mkdtemp()
            in_path = os.path.join(tmpdir, f"{uuid.uuid4()}.gml")
            total = 0
            with open(in_path, "wb") as f_dst:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    total += len(chunk)
                    f_dst.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="アップロードされたファイルが空です。")
            print(f"[UPLOAD] /api/citygml/to-step: received {total} bytes -> {in_path}")
        else:
            in_path = gml_path  # type: ignore
            if not os.path.exists(in_path):
                raise HTTPException(status_code=404, detail=f"指定されたパスが見つかりません: {in_path}")
            print(f"[UPLOAD] /api/citygml/to-step: using local path {in_path}")

        # limitが0または負数の場合は警告（大容量ファイルの場合）
        if limit is not None and limit <= 0:
            # 135MBのファイルなど大きい場合は制限を推奨
            if file is not None and file.size and file.size > 50 * 1024 * 1024:  # 50MB以上
                raise HTTPException(
                    status_code=400, 
                    detail="大容量ファイルの場合は建物数制限（limit）を設定してください（推奨: 10-50）"
                )
        
        # 出力パス
        out_dir = tempfile.mkdtemp()
        out_path = os.path.join(out_dir, f"citygml_{uuid.uuid4().hex[:8]}.step")

        ok, msg = export_step_from_citygml(
            in_path,
            out_path,
            default_height=default_height,
            limit=limit,
            debug=debug,
            method=method,
            sew_tolerance=sew_tolerance,
            reproject_to=reproject_to,
            source_crs=source_crs,
            auto_reproject=auto_reproject,
        )
        if not ok:
            raise HTTPException(status_code=400, detail=f"変換に失敗しました: {msg}")

        # ファイル内容を読み込んでからレスポンスとして返す
        with open(out_path, 'rb') as f:
            content = f.read()
        
        # 一時ファイルをクリーンアップ
        try:
            os.remove(out_path)
            os.rmdir(out_dir)
        except:
            pass
        
        # StreamingResponseを使用してメモリ効率を改善
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={os.path.basename(out_path)}",
                "Content-Length": str(len(content)),
                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                "Access-Control-Allow-Credentials": "true",
                "Cache-Control": "no-cache"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")


# --- CityGML 検証（簡易） ---
@router.post("/api/citygml/validate")
async def citygml_validate(
    file: Optional[UploadFile] = File(None),
    gml_path: Optional[str] = Form(None),
    limit: Optional[int] = Form(10),
):
    """
    CityGML が当モジュールのヒューリスティックに適合するか簡易チェックします。
    - bldg:Building が存在し、フットプリント多角形が取得できるかを確認
    """
    try:
        if file is None and not gml_path:
            raise HTTPException(status_code=400, detail="CityGMLファイルをアップロードするか gml_path を指定してください。")

        if file is not None:
            tmpdir = tempfile.mkdtemp()
            in_path = os.path.join(tmpdir, f"{uuid.uuid4()}.gml")
            total = 0
            with open(in_path, "wb") as f_dst:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    total += len(chunk)
                    f_dst.write(chunk)
            if total == 0:
                raise HTTPException(status_code=400, detail="アップロードされたファイルが空です。")
            print(f"[UPLOAD] /api/citygml/validate: received {total} bytes -> {in_path}")
        else:
            in_path = gml_path  # type: ignore
            if not os.path.exists(in_path):
                raise HTTPException(status_code=404, detail=f"指定されたパスが見つかりません: {in_path}")
            print(f"[UPLOAD] /api/citygml/validate: using local path {in_path}")

        fps = parse_citygml_footprints(in_path, limit=limit or None)
        return {
            "valid": len(fps) > 0,
            "buildings_with_footprints": len(fps),
            "sample_building_id": fps[0].building_id if fps else None,
            "notes": "footprint+height extrusion heuristic",
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"検証でエラー: {str(e)}")

# --- ヘルスチェック ---
@router.get("/api/health", status_code=200)
async def api_health_check():
    return {
        "status": "healthy" if OCCT_AVAILABLE else "degraded",
        "version": "1.0.0",
        "opencascade_available": OCCT_AVAILABLE,
        "supported_formats": ["step", "stp", "brep"] if OCCT_AVAILABLE else [],
        "features": {
            "step_to_svg_unfold": OCCT_AVAILABLE,
            "face_numbering": True,
            "multi_page_layout": True,
            "canvas_layout": True,
            "paged_layout": True
        }
    }
