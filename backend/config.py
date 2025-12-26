import os
import builtins
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 環境変数でdemo/productionモードの場合、printを無効化してパフォーマンス向上
ENV = os.getenv("ENV", os.getenv("PYTHON_ENV", "development"))

if ENV in ["demo", "production"]:
    def noop_print(*args, **kwargs):
        pass
    builtins.print = noop_print
    # 起動時のメッセージのみ標準エラー出力に表示
    sys.stderr.write(f"[CONFIG] {ENV}モード: ログ出力を無効化しました\n")

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

    # ENV変数は冒頭で定義済み（print無効化のため）
    # 環境に応じた.envファイルを選択
    env_file = None
    if ENV == "production":
        # 本番環境: .env.production → .env の順で探す
        if os.path.exists(".env.production"):
            env_file = ".env.production"
        elif os.path.exists(".env"):
            env_file = ".env"
    elif ENV == "demo":
        # デモ環境: .env.demo → .env の順で探す
        if os.path.exists(".env.demo"):
            env_file = ".env.demo"
        elif os.path.exists(".env"):
            env_file = ".env"
    else:
        # 開発環境（デフォルト）: .env.development → .env の順で探す
        if os.path.exists(".env.development"):
            env_file = ".env.development"
        elif os.path.exists(".env"):
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
    "title": "Paper-CAD Backend API",
    "description": """
**Paper-CAD Backend API**: 3D CAD to 2D papercraft conversion service

## 主な機能 / Features

### 🏗️ STEP File Unfolding
- 3D STEP files → 2D SVG/PDF papercraft templates (展開図生成)
- Multi-page layout support (A4/A3/Letter formats)
- Configurable scale and precision

### 🏙️ CityGML to STEP Conversion
- LOD1/LOD2/LOD3 support with hierarchical fallback
- BuildingPart merging with Boolean fusion
- XLink reference resolution
- Modular architecture: 27 components across 7 layers (Issue #129)

### 🇯🇵 PLATEAU Integration
- Japan PLATEAU 3D city data integration
- Address/facility-based building search
- Automatic geocoding and CRS transformation
- One-step fetch & convert workflow

### 📐 Advanced Processing
- Adaptive tolerance computation
- Progressive geometry repair (4-stage escalation)
- Coordinate recentering for precision
- Multiple conversion methods (solid/sew/extrude/auto)
    """,
    "version": "1.0.0",
    "contact": {
        "name": "Kodai MIYAZAKI",
        "url": "https://github.com/Soynyuu/Paper-CAD"
    },
    "license_info": {
        "name": "MIT",
    }
}

# OpenAPI タグのメタデータ
TAGS_METADATA = [
    {
        "name": "STEP Processing",
        "description": "STEP file unfolding to SVG/PDF papercraft templates (STEP → 展開図変換)",
        "externalDocs": {
            "description": "STEP format documentation",
            "url": "https://en.wikipedia.org/wiki/ISO_10303-21",
        },
    },
    {
        "name": "SVG Processing",
        "description": "SVG to PDF conversion (SVG → PDF変換)",
    },
    {
        "name": "CityGML Processing",
        "description": "CityGML to STEP conversion with LOD1/LOD2/LOD3 support (CityGML → STEP変換)",
        "externalDocs": {
            "description": "CityGML documentation",
            "url": "https://www.ogc.org/standards/citygml",
        },
    },
    {
        "name": "PLATEAU Integration",
        "description": "Japan PLATEAU 3D city data integration and search (日本のPLATEAU 3D都市データ統合)",
        "externalDocs": {
            "description": "PLATEAU official site",
            "url": "https://www.mlit.go.jp/plateau/",
        },
    },
    {
        "name": "System",
        "description": "Health checks, diagnostics, and system information (ヘルスチェック、診断、システム情報)",
    },
]


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
    app = FastAPI(**APP_CONFIG, openapi_tags=TAGS_METADATA)
    setup_cors(app)
    return app
