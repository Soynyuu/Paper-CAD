import os
import uvicorn
from config import create_app, OCCT_AVAILABLE
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from api.endpoints import router

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
    import logging
    logger = logging.getLogger(__name__)

    try:
        from services.plateau_api_client import _get_cached_mesh2_map
        await _get_cached_mesh2_map()
        logger.info("✅ PLATEAU mesh2->municipality map initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize PLATEAU mesh mapping: {e}")
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

# 簡易アクセスログ用ミドルウェア（1行/リクエスト）
@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start = time.time()
    try:
        response = await call_next(request)
        dur = (time.time() - start) * 1000.0
        try:
            client = f"{request.client.host}:{request.client.port}" if request.client else "-"
        except Exception:
            client = "-"
        print(f"[ACCESS] {client} {request.method} {request.url.path} -> {response.status_code} {dur:.1f}ms")
        return response
    except Exception as e:
        dur = (time.time() - start) * 1000.0
        print(f"[ACCESS][ERROR] {request.method} {request.url.path} after {dur:.1f}ms: {e}")
        raise

def main():
    """サーバーを起動する"""
    if not OCCT_AVAILABLE:
        print("警告: OpenCASCADE が利用できないため、一部機能が制限されます。")

    # 環境変数から設定を取得
    port = int(os.getenv("PORT", 8001))
    env = os.getenv("ENV", os.getenv("PYTHON_ENV", "development"))
    is_production_like = env in ["production", "demo"]  # demo も本番設定を使用

    # 本番環境またはデモ環境ではreloadを無効化、ワーカー数を設定
    reload_enabled = not is_production_like
    workers = int(os.getenv("WORKERS", 1 if not is_production_like else 2))

    print(f"\n{'='*60}")
    print(f"[SERVER] 環境: {env}")
    print(f"[SERVER] ポート: {port}")
    print(f"[SERVER] リロード: {reload_enabled}")
    print(f"[SERVER] ワーカー数: {workers}")
    print(f"[SERVER] OpenCASCADE: {'利用可能' if OCCT_AVAILABLE else '利用不可'}")
    if env == "demo":
        print(f"[SERVER] 💡 デモモード: 本番パフォーマンス + localhost対応")
    print(f"{'='*60}\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        workers=workers if not reload_enabled else None,  # reloadモードではworkersは使えない
        access_log=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
