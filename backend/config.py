import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# OpenCASCADE Technology (OCCT) の可用性チェック
try:
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core import BRepTools
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE
    from OCC.Core.BRepGProp import BRepGProp_Face
    from OCC.Core import BRepGProp
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomLProp import GeomLProp_SLProps
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Edge, TopoDS_Vertex
    from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Pln, gp_Cylinder, gp_Cone, gp_Trsf, gp_Ax1, gp_Ax2, gp_Ax3
    from OCC.Core.Geom import Geom_Surface, Geom_Plane, Geom_CylindricalSurface, Geom_ConicalSurface
    from OCC.Core.Standard import Standard_Failure
    OCCT_AVAILABLE = True
except ImportError as e:
    OCCT_AVAILABLE = False


# 環境変数の読み込み
try:
    from dotenv import load_dotenv
    load_dotenv()  # .envファイルの環境変数を読み込む
except ImportError:
    print("python-dotenvがインストールされていないため、環境変数の読み込みをスキップします。")

# 設定値
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"

# アプリケーション設定
APP_CONFIG = {
    "title": "unfold-step2svg",
    "description": "unfold step model to svg",
    "version": "1.0.0",
    "contact": {
        "name": "Kodai MIYAZAKI",
    }
}


def setup_cors(app: FastAPI) -> None:
    """CORS設定を行う"""
    print(f"フロントエンドURL: {FRONTEND_URL}")
    print(f"すべてのオリジンを許可: {CORS_ALLOW_ALL}")
    
    if CORS_ALLOW_ALL or FRONTEND_URL == "*":
        # 開発環境: すべてのオリジンを許可
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # すべてのオリジンを許可
            allow_credentials=True,
            allow_methods=["*"],  
            allow_headers=["*"],  
        )
        print("CORS: すべてのオリジンを許可します")
    else:
        # 本番環境: 特定のオリジンのみを許可
        # ホスト名のバリエーションを追加
        origins = []
        
        # FRONTENDを設定
        if FRONTEND_URL:
            origins.append(FRONTEND_URL)
        
        origins.extend([
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "https://paper-cad.soynyuu.com",
            "https://backend-diorama.soynyuu.com"
        ])
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        print(f"CORS: 以下のオリジンを許可します: {origins}")

def create_app() -> FastAPI:
    """FastAPIアプリケーションを作成する"""
    app = FastAPI(**APP_CONFIG)
    setup_cors(app)
    return app