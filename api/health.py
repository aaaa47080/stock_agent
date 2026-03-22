"""Health check endpoints for load balancing and monitoring."""

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import api.globals as globals

router = APIRouter(tags=["health"])

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()


@router.get("/health")
async def health_check():
    """Basic health check — verifies application and database are responsive."""
    checks = {"app": True}

    try:
        from core.database import get_connection

        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    all_ok = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "healthy" if all_ok else "degraded",
            "service": "pi_crypto_insight",
            "uptime_seconds": int(time.time() - SERVICE_START_TIME),
            "checks": checks,
        },
    )


@router.get("/ready")
async def readiness_check():
    """
    Readiness check — confirms the service can accept requests.
    Verifies critical components are initialized.
    """
    ready = True
    components = {}

    # 檢查 OKX Connector
    components["okx_connector"] = globals.okx_connector is not None

    # 檢查數據庫
    try:
        from core.database import get_connection

        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        components["database"] = True
    except Exception:
        components["database"] = False
        ready = False

    status_code = 200 if ready else 503

    return JSONResponse(
        content={
            "status": "ready" if ready else "not_ready",
            "components": components,
            "uptime_seconds": int(time.time() - SERVICE_START_TIME),
        },
        status_code=status_code,
    )
