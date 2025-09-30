import os
import uvicorn
from config import create_app, OCCT_AVAILABLE
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.endpoints import router

# FastAPIアプリケーションの作成
app = create_app()

# APIルーターの追加
app.include_router(router)

# ルートパスでindex.htmlを返す
@app.get("/")
async def read_index():
    return FileResponse("index.html")

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
    
    port = int(os.getenv("PORT", 8001))
    print(f"サーバーをポート {port} で起動します。")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        access_log=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
