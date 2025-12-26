from fastapi import APIRouter

from config import OCCT_AVAILABLE

router = APIRouter()


# --- ヘルスチェック ---
@router.get(
    "/api/health",
    summary="Health Check",
    tags=["System"],
    status_code=200,
    responses={
        200: {
            "description": "System health status and available features",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "opencascade_available": True,
                        "supported_formats": ["STEP", "BREP", "CityGML", "PLATEAU"],
                        "features": {
                            "step_unfold": True,
                            "citygml_conversion": True,
                            "plateau_integration": True,
                            "pdf_export": True
                        }
                    }
                }
            }
        }
    }
)
async def api_health_check():
    """
    システムのヘルスチェックと利用可能な機能を返します。

    System health check and available features.

    **ステータス / Status**:
    - `healthy`: すべての機能が利用可能 / All features available
    - `degraded`: OpenCASCADE未利用、一部機能制限 / OCCT unavailable, limited features

    **機能フラグ / Feature Flags**:
    - `step_unfold`: STEP → SVG/PDF展開図生成 / STEP to SVG/PDF unfold
    - `citygml_conversion`: CityGML → STEP変換 / CityGML to STEP conversion
    - `plateau_integration`: PLATEAU API統合 / PLATEAU API integration
    - `pdf_export`: PDF出力機能 / PDF export functionality

    **用途 / Use Cases**:
    - サーバーの起動確認 / Server startup verification
    - 機能の利用可否チェック / Feature availability check
    - モニタリング・ヘルスチェック / Monitoring health checks
    """
    return {
        "status": "healthy" if OCCT_AVAILABLE else "degraded",
        "opencascade_available": OCCT_AVAILABLE,
        "supported_formats": ["STEP", "BREP", "CityGML", "PLATEAU"] if OCCT_AVAILABLE else [],
        "features": {
            "step_unfold": OCCT_AVAILABLE,
            "citygml_conversion": OCCT_AVAILABLE,
            "plateau_integration": True,
            "pdf_export": OCCT_AVAILABLE
        }
    }


# --- デバッグ: CORS設定確認 ---
@router.get(
    "/api/debug/cors-config",
    summary="CORS Configuration Debug",
    tags=["System"],
    include_in_schema=False,  # 本番ドキュメントから除外 / Exclude from production docs
)
async def debug_cors_config():
    """
    CORS設定の診断情報を返す（デバッグ用）

    Returns CORS configuration diagnostic information (for debugging only).

    **警告 / Warning**:
    - 本番環境では検証後にこのエンドポイントを削除することを推奨
    - Recommend removing this endpoint after validation in production
    - `include_in_schema=False` により Swagger UI には表示されません
    - Not visible in Swagger UI due to `include_in_schema=False`

    **診断情報 / Diagnostic Info**:
    - 現在のCORS設定 / Current CORS settings
    - 環境変数の値 / Environment variable values
    - レスポンスヘッダーのプレビュー / Response header preview
    """
    import os
    from config import FRONTEND_URL, CORS_ALLOW_ALL

    # 環境変数の生の値を取得
    raw_frontend_url = os.getenv("FRONTEND_URL")
    raw_cors_allow_all = os.getenv("CORS_ALLOW_ALL")

    # 設定の解釈結果
    is_dev_mode = CORS_ALLOW_ALL or FRONTEND_URL == "*"
    cors_mode = "development (localhost only)" if is_dev_mode else "production (restricted origins)"

    # 許可されるオリジンを構築（config.pyと同じロジック）
    if is_dev_mode:
        allowed_origins = [
            "http://localhost:8001",
            "http://127.0.0.1:8001",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
        ]
    else:
        allowed_origins = [
            "https://paper-cad.soynyuu.com",
            "https://app-paper-cad.soynyuu.com",
        ]
        if FRONTEND_URL and FRONTEND_URL != "*":
            if FRONTEND_URL not in allowed_origins:
                allowed_origins.insert(0, FRONTEND_URL)

    return {
        "cors_configuration": {
            "mode": cors_mode,
            "frontend_url": FRONTEND_URL,
            "cors_allow_all": CORS_ALLOW_ALL,
            "is_production_safe": not is_dev_mode,
            "allowed_origins": allowed_origins,
            "allows_credentials": True
        },
        "environment_variables": {
            "FRONTEND_URL": raw_frontend_url,
            "CORS_ALLOW_ALL": raw_cors_allow_all
        },
        "expected_response_headers": {
            "access-control-allow-origin": f"{allowed_origins[0]} (or matching request origin)",
            "access-control-allow-credentials": "true",
            "access-control-allow-methods": "*",
            "access-control-allow-headers": "*"
        },
        "security_notes": {
            "wildcard_not_used": "Wildcard origin (*) is never used with credentials for security compliance",
            "rfc_6454_compliance": "Complies with CORS spec (RFC 6454) - no wildcard + credentials combination"
        },
        "warning": "This endpoint should be removed in production after verification"
    }
