import os
import uvicorn
from config import create_app, OCCT_AVAILABLE
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from api.endpoints import router
from utils.logger import get_logger

logger = get_logger(__name__)

# FastAPIアプリケーションの作成
app = create_app()

# APIルーターの追加
app.include_router(router)


# 起動時の初期化処理
@app.on_event("startup")
async def startup_event():
    """
    サーバー起動時に実行される初期化処理

    - PLATEAU mesh2->municipality マッピングの構築
    """
    try:
        from services.plateau_api_client import _get_cached_mesh2_map

        await _get_cached_mesh2_map()
        logger.info("PLATEAU mesh2->municipality map initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize PLATEAU mesh mapping: %s", e)
        logger.warning("PLATEAU search functionality may be limited")


# ルートパスでAPI情報を返す
@app.get("/")
async def read_index():
    return {
        "service": "Paper-CAD Backend API",
        "health": "/api/health",
        "docs": "/docs",
    }


# 静的ファイルの配信（CSSやJSなどの追加リソース用）
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

try:
    from services.local_demo import (
        LOCAL_DEMO_ROUTE_PREFIX,
        LocalDemoStaticFiles,
        get_local_demo_static_dir,
        is_local_demo,
    )

    local_demo_dir = get_local_demo_static_dir()
    if is_local_demo() and local_demo_dir.exists():
        app.mount(
            LOCAL_DEMO_ROUTE_PREFIX,
            LocalDemoStaticFiles(directory=str(local_demo_dir)),
            name="local-demo-cache",
        )
        logger.info("Mounted local demo cache at %s from %s", LOCAL_DEMO_ROUTE_PREFIX, local_demo_dir)
except Exception as e:
    logger.warning("Local demo cache was not mounted: %s", e)


# 簡易アクセスログ用ミドルウェア（1行/リクエスト）
@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time

    start = time.time()
    try:
        response = await call_next(request)
        dur = (time.time() - start) * 1000.0
        try:
            client = (
                f"{request.client.host}:{request.client.port}"
                if request.client
                else "-"
            )
        except Exception:
            client = "-"
        logger.info(
            "[ACCESS] %s %s %s -> %s %.1fms",
            client,
            request.method,
            request.url.path,
            response.status_code,
            dur,
        )
        return response
    except Exception as e:
        dur = (time.time() - start) * 1000.0
        logger.error(
            "[ACCESS] %s %s after %.1fms: %s", request.method, request.url.path, dur, e
        )
        raise


def main():
    """サーバーを起動する"""
    if not OCCT_AVAILABLE:
        logger.warning("OpenCASCADE が利用できないため、一部機能が制限されます。")

    # 環境変数から設定を取得
    port = int(os.getenv("PORT", 8001))
    env = os.getenv("ENV", os.getenv("PYTHON_ENV", "development"))
    is_production_like = env in ["production", "demo", "local_demo"]  # demo も本番設定を使用

    # 本番環境またはデモ環境ではreloadを無効化、ワーカー数を設定
    reload_enabled = not is_production_like
    workers = int(os.getenv("WORKERS", 1 if not is_production_like else 2))

    logger.info(
        "SERVER: 環境=%s, ポート=%d, リロード=%s, ワーカー数=%d, OpenCASCADE=%s",
        env,
        port,
        reload_enabled,
        workers,
        "利用可能" if OCCT_AVAILABLE else "利用不可",
    )
    if env == "demo":
        logger.info("SERVER: デモモード: 本番パフォーマンス + localhost対応")
    elif env == "local_demo":
        logger.info("SERVER: ローカルデモモード: 本番パフォーマンス + オフラインキャッシュ対応")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        workers=workers
        if not reload_enabled
        else None,  # reloadモードではworkersは使えない
        access_log=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
