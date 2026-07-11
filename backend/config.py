import os
from pathlib import Path
from typing import Callable, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.logger import get_logger

logger = get_logger(__name__)

ENV = os.getenv("ENV", os.getenv("PYTHON_ENV", "development"))

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
    from OCC.Core.GeomAbs import (
        GeomAbs_Plane,
        GeomAbs_Cylinder,
        GeomAbs_Cone,
        GeomAbs_Sphere,
    )
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Edge, TopoDS_Vertex
    from OCC.Core.gp import (
        gp_Pnt,
        gp_Vec,
        gp_Dir,
        gp_Pln,
        gp_Cylinder,
        gp_Cone,
        gp_Trsf,
        gp_Ax1,
        gp_Ax2,
        gp_Ax3,
    )
    from OCC.Core.Geom import (
        Geom_Surface,
        Geom_Plane,
        Geom_CylindricalSurface,
        Geom_ConicalSurface,
    )
    from OCC.Core.Standard import Standard_Failure

    OCCT_AVAILABLE = True
except ImportError as e:
    OCCT_AVAILABLE = False


# 環境変数の読み込み
try:
    from dotenv import load_dotenv

    # ENV変数は冒頭で定義済み
    # 環境に応じた.envファイルを選択
    env_file = None
    if ENV == "production":
        # 本番環境: .env.production → .env の順で探す
        if os.path.exists(".env.production"):
            env_file = ".env.production"
        elif os.path.exists(".env"):
            env_file = ".env"
    elif ENV in {"demo", "local_demo"}:
        # デモ環境: .env.demo/.env.local_demo → .env の順で探す
        local_env_file = f".env.{ENV}"
        if os.path.exists(local_env_file):
            env_file = local_env_file
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
        logger.info("環境変数を %s から読み込みました (ENV=%s)", env_file, ENV)
    else:
        logger.info(
            "環境変数ファイルが見つかりません (ENV=%s)。環境変数から直接読み込みます。",
            ENV,
        )
except ImportError:
    logger.warning(
        "python-dotenvがインストールされていないため、環境変数の読み込みをスキップします。"
    )

# 設定値
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"

# CityGML Cache Configuration (Optional, for Tokyo 23 wards)
CITYGML_CACHE_ENABLED = os.getenv("CITYGML_CACHE_ENABLED", "false").lower() == "true"
DEFAULT_CITYGML_CACHE_DIR = Path(__file__).resolve().parent / "data" / "citygml_cache"
CITYGML_CACHE_DIR = os.getenv("CITYGML_CACHE_DIR", str(DEFAULT_CITYGML_CACHE_DIR))

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
        "url": "https://github.com/Soynyuu/Paper-CAD",
    },
    "license_info": {
        "name": "AGPL-3.0",
    },
}


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


SVG_UPLOAD_LIMITS = {
    "max_files": _get_int_env("SVG_MAX_FILES", 100),
    "max_file_size_bytes": _get_int_env("SVG_MAX_FILE_SIZE_MB", 50) * 1024 * 1024,
    "max_total_bytes": _get_int_env("SVG_MAX_TOTAL_SIZE_MB", 200) * 1024 * 1024,
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
    logger.info(
        "CORS CONFIG: フロントエンドURL=%s, すべてのオリジンを許可=%s, 環境=%s",
        FRONTEND_URL,
        CORS_ALLOW_ALL,
        os.getenv("ENV", "development"),
    )

    # オリジンリストを構築
    origins = []
    env = os.getenv("ENV", os.getenv("PYTHON_ENV", "development"))

    if CORS_ALLOW_ALL or FRONTEND_URL == "*":
        # 開発環境: ローカルホストを明示的に許可
        # セキュリティ上の理由から、allow_origins=["*"]とallow_credentials=Trueの
        # 組み合わせは使用しない（CORS仕様違反、ブラウザでブロックされる）
        origins.extend(
            [
                "http://localhost:8001",
                "http://127.0.0.1:8001",
                "http://localhost:8080",
                "http://127.0.0.1:8080",
                "http://localhost:8081",
                "http://127.0.0.1:8081",
            ]
        )
        logger.info("CORS: 開発モード: ローカルホストのみ許可")
    elif env == "demo":
        # デモ環境: 本番設定 + localhost許可
        if FRONTEND_URL and FRONTEND_URL != "*":
            origins.append(FRONTEND_URL)

        # localhostを追加（デモ用）
        origins.extend(
            [
                "http://localhost:8080",
                "http://127.0.0.1:8080",
            ]
        )

        # 本番ドメインも追加（オプション）
        origins.extend(
            [
                "https://paper-cad.soynyuu.com",
                "https://app-paper-cad.soynyuu.com",
            ]
        )
        logger.info("CORS: デモモード: 本番設定 + localhost許可")
    else:
        # 本番環境: 特定のオリジンのみを許可
        if FRONTEND_URL and FRONTEND_URL != "*":
            origins.append(FRONTEND_URL)

        # 本番ドメインを追加
        origins.extend(
            [
                "https://paper-cad.soynyuu.com",
                "https://app-paper-cad.soynyuu.com",
            ]
        )
        logger.info("CORS: 本番モード: 特定のオリジンのみ許可")

    # CORSミドルウェアを追加
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-LOD-Requested", "X-LOD-Used", "X-LOD-Fallback"],
    )

    logger.info("CORS: 許可されたオリジン数=%d: %s", len(origins), origins)


def create_app(lifespan: Optional[Callable] = None) -> FastAPI:
    """FastAPIアプリケーションを作成する"""
    app = FastAPI(
        **APP_CONFIG,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )
    setup_cors(app)
    return app
