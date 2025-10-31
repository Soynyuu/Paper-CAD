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
    import os as _os

    # ENV環境変数で実行環境を判定（development/production/demo）
    # デフォルトは development
    ENV = _os.getenv("ENV", _os.getenv("PYTHON_ENV", "development"))

    # 環境に応じた.envファイルを選択
    env_file = None
    if ENV == "production":
        # 本番環境: .env.production → .env の順で探す
        if _os.path.exists(".env.production"):
            env_file = ".env.production"
        elif _os.path.exists(".env"):
            env_file = ".env"
    elif ENV == "demo":
        # デモ環境: .env.demo → .env の順で探す
        if _os.path.exists(".env.demo"):
            env_file = ".env.demo"
        elif _os.path.exists(".env"):
            env_file = ".env"
    else:
        # 開発環境（デフォルト）: .env.development → .env の順で探す
        if _os.path.exists(".env.development"):
            env_file = ".env.development"
        elif _os.path.exists(".env"):
            env_file = ".env"

    if env_file:
        load_dotenv(env_file)
        print(f"[CONFIG] 環境変数を {env_file} から読み込みました (ENV={ENV})")
    else:
        print(f"[CONFIG] 環境変数ファイルが見つかりません (ENV={ENV})。環境変数から直接読み込みます。")
except ImportError:
    print("[CONFIG] python-dotenvがインストールされていないため、環境変数の読み込みをスキップします。")

# 設定値
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"

# アプリケーション設定
APP_CONFIG = {
    "title": "Paper-CAD",
    "description": "Paper-CAD Backend API - STEP to SVG unfold service",
    "version": "1.0.0",
    "contact": {
        "name": "Kodai MIYAZAKI",
    }
}


def setup_cors(app: FastAPI) -> None:
    """CORS設定を行う"""
    print(f"\n{'='*60}")
    print(f"[CORS CONFIG] フロントエンドURL: {FRONTEND_URL}")
    print(f"[CORS CONFIG] すべてのオリジンを許可: {CORS_ALLOW_ALL}")
    print(f"[CORS CONFIG] 環境: {os.getenv('ENV', 'development')}")
    print(f"{'='*60}\n")

    # オリジンリストを構築
    origins = []
    env = os.getenv('ENV', os.getenv('PYTHON_ENV', 'development'))

    if CORS_ALLOW_ALL or FRONTEND_URL == "*":
        # 開発環境: ローカルホストを明示的に許可
        # セキュリティ上の理由から、allow_origins=["*"]とallow_credentials=Trueの
        # 組み合わせは使用しない（CORS仕様違反、ブラウザでブロックされる）
        origins.extend([
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
        ])
        print("[CORS] 🔧 開発モード: ローカルホストのみ許可")
    elif env == "demo":
        # デモ環境: 本番設定 + localhost許可
        # FRONTENDを設定
        if FRONTEND_URL and FRONTEND_URL != "*":
            origins.append(FRONTEND_URL)

        # localhostを追加（デモ用）
        origins.extend([
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ])

        # 本番ドメインも追加（オプション）
        origins.extend([
            "https://paper-cad.soynyuu.com",
            "https://app-paper-cad.soynyuu.com",
        ])
        print(f"[CORS] 🎬 デモモード: 本番設定 + localhost許可")
    else:
        # 本番環境: 特定のオリジンのみを許可
        # FRONTENDを設定
        if FRONTEND_URL and FRONTEND_URL != "*":
            origins.append(FRONTEND_URL)

        # 本番ドメインを追加
        origins.extend([
            "https://paper-cad.soynyuu.com",
            "https://app-paper-cad.soynyuu.com",
        ])
        print(f"[CORS] 🔒 本番モード: 特定のオリジンのみ許可")

    # CORSミドルウェアを追加
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    print(f"[CORS] 許可されたオリジン数: {len(origins)}")
    for i, origin in enumerate(origins, 1):
        print(f"[CORS]   {i}. {origin}")

def create_app() -> FastAPI:
    """FastAPIアプリケーションを作成する"""
    app = FastAPI(**APP_CONFIG)
    setup_cors(app)
    return app