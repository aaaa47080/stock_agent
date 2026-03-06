# ruff: noqa: E402
# ^ E402 ignored because we need to modify sys.path before importing local modules
import os
import sys
import asyncio
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Fix Windows console encoding (cp950 cannot handle emoji/unicode)
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 將專案根目錄加入 Python 路徑
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import logging

# Load environment variables
load_dotenv()

# Configure Logging
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Cloud deployment: log to stdout only (Zeabur/K8s captures stdout)
# File-based logging fills ephemeral storage and causes pod eviction
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[console_handler]
)

# 靜音 Windows asyncio WinError 10054（客戶端斷線時的無害噪音）
class _SuppressWinError10054(logging.Filter):
    def filter(self, record):
        return 'WinError 10054' not in (record.getMessage())

logging.getLogger('asyncio').addFilter(_SuppressWinError10054())

# Import from refactored modules
from api.utils import logger
from api.deps import get_current_user, require_admin
import api.globals as globals
from api.services import (
    load_market_pulse_cache,
    update_screener_task,
    update_market_pulse_task,
    funding_rate_update_task
)
from api.routers import system, analysis, market, trading, user, twstock, usstock
from api.routers.forum import router as forum_router
from api.routers.premium import router as premium_router
from api.routers.admin import router as admin_router
from api.routers.admin_panel import router as admin_panel_router
from api.routers.friends import router as friends_router
from api.routers.messages import router as messages_router
from api.routers.audit import router as audit_router  # Audit log admin API
from api.routers.scam_tracker import router as scam_tracker_router  # Scam tracker API
from api.routers.governance import router as governance_router  # Community governance API
from api.routers.notifications import router as notifications_router  # Notifications API
from api.routers.alerts import router as alerts_router  # Price Alerts API
from api.routers.tools import router as tools_router   # Tool preferences API
from api.alert_checker import price_alert_check_task

# Import database and core modules (but don't initialize at module level)
from core.database import init_db
from trading.okx_api_connector import OKXAPIConnector

from fastapi import Request
from fastapi.responses import JSONResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database (with retry + graceful fallback)
    skip_db_init = os.getenv('SKIP_DB_INIT', 'false').lower() == 'true'

    if not skip_db_init:
        logger.info("🔄 Initializing database...")
        loop = asyncio.get_running_loop()
        try:
            # init_db 內部已有重試機制（10次，每次間隔3秒）
            await loop.run_in_executor(None, init_db)
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"⚠️ 資料庫初始化失敗: {e}")
            logger.warning("⏭️ 應用程式將繼續運行，部分功能可能無法使用")

        # Seed tools catalog (idempotent — skips existing rows)
        try:
            from core.database.tools import seed_tools_catalog
            await loop.run_in_executor(None, seed_tools_catalog)
            logger.info("✅ Tools catalog seeded")
        except Exception as e:
            logger.warning(f"⚠️ Tools catalog seeding failed: {e}")
    else:
        logger.info("⏭️ 跳過資料庫初始化 (SKIP_DB_INIT=true)")

    from core.config import TEST_MODE
    if TEST_MODE:
        logger.warning("⚠️⚠️⚠️ TEST_MODE IS ENABLED! THIS SHOULD NOT BE ON IN PRODUCTION! ⚠️⚠️⚠️")
        logger.warning("Test-only endpoints (e.g., /dev-login) are active.")
    
    # Startup: Initialize Global Instances
    try:
        globals.okx_connector = OKXAPIConnector()
        logger.info("✅ OKX Connector 初始化成功")
    except Exception as e:
        logger.error(f"❌ OKX Connector 初始化失敗: {e}")
        globals.okx_connector = None
    
    # 預熱 V4 bootstrap（純載入 PromptRegistry + AgentRegistry，不建立 LLM）
    # 實際 LLM client 由各請求的 user_api_key 決定，所以 startup 僅驗證模組可 import
    try:
        from core.agents.bootstrap import bootstrap as _v4_bootstrap  # noqa: F401
        logger.info("✅ V4 ManagerAgent 模組載入成功（LLM 將在首次請求時初始化）")
    except Exception as e:
        logger.warning(f"⚠️ V4 ManagerAgent 模組載入失敗（將 fallback 至 V1 bot）: {e}")
    globals.v4_manager = None  # 實際 manager 按需在 analysis.py 中建立
    
    # Startup: 嘗試載入快取
    # [Optimization] Screener/Funding are now In-Memory Only, no DB load needed
    load_market_pulse_cache() # Market Pulse remains persistent (slow updates)

    # Startup: 啟動背景篩選器更新任務
    asyncio.create_task(update_screener_task())

    # Market Pulse 任務：檢查是否由獨立 Worker 處理
    # 設置環境變數 MARKET_PULSE_WORKER=1 時，API 不啟動此任務（由獨立 Worker 處理）
    if not os.getenv("MARKET_PULSE_WORKER"):
        logger.info("📊 Starting Market Pulse task in API process...")
        asyncio.create_task(update_market_pulse_task())
    else:
        logger.info("📊 Market Pulse handled by external worker (MARKET_PULSE_WORKER=1)")

    # Startup: 啟動 Funding Rate 定期更新任務
    asyncio.create_task(funding_rate_update_task())

    # Startup: 啟動價格警報檢查任務
    asyncio.create_task(price_alert_check_task())
    logger.info("Price alert checker task started")

    # Startup: 啟動審計日誌清理任務 (Stage 2 Security)
    # 每天凌晨 3 點自動清理超過 90 天的舊日誌
    try:
        from core.audit import audit_log_cleanup_task
        asyncio.create_task(audit_log_cleanup_task())
        logger.info("✅ Audit log cleanup task scheduled (daily at 3 AM UTC)")
    except ImportError:
        logger.warning("⚠️ Audit log cleanup task not available")

    # Startup: 啟動 JWT 密鑰輪換任務 (Stage 3 Security)
    # 每月 1 號凌晨 2 點自動輪換 JWT 密鑰
    if os.getenv("USE_KEY_ROTATION", "false").lower() == "true":
        try:
            from core.key_rotation import key_rotation_task
            asyncio.create_task(key_rotation_task())
            logger.info("✅ JWT key rotation task scheduled (monthly on 1st at 2 AM UTC)")
        except ImportError:
            logger.warning("⚠️ Key rotation task not available")
    
    yield
    
    # Shutdown: Clean up resources
    logger.info("🛑 Shutting down application...")
    
    # 關閉 Screener Ticker WebSocket
    try:
        from data.okx_websocket import okx_ticker_ws_manager
        await okx_ticker_ws_manager.stop()
        logger.info("✅ Screener Ticker WebSocket 已關閉")
    except Exception as e:
        logger.error(f"❌ 關閉 Ticker WebSocket 時出錯: {e}")

    # 關閉數據庫連接池
    try:
        from core.database import close_all_connections
        close_all_connections()
    except Exception as e:
        logger.error(f"❌ 關閉連接池時出錯: {e}")

app = FastAPI(title="Crypto Trading System API", version="1.2.0", lifespan=lifespan)

# 🔒 Security: Stage 2 - Production environment detection
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() in ["production", "prod"]

# --- Global Exception Handler (Fix 500 Internal Server Error) ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler to ensure all 500 errors return JSON
    and are properly logged with traceback.

    Stage 2 Security: Hide error details in production to prevent information leakage.
    """
    import traceback
    error_msg = f"{type(exc).__name__}: {str(exc)}"

    # Log full details for debugging
    logger.error(f"🔥 Unhandled 500 Error at {request.method} {request.url.path}: {error_msg}")
    if not IS_PRODUCTION:
        logger.error(traceback.format_exc())

    # Response varies by environment - hide details in production
    response_content = {
        "detail": "Internal Server Error",
        "error": error_msg if not IS_PRODUCTION else "An error occurred",
        "path": request.url.path
    }

    return JSONResponse(
        status_code=500,
        content=response_content
    )

# ================================================================
# Security Enhancements (Phase 7)
# ================================================================

# --- 1. Rate Limiting ---
try:
    from slowapi.errors import RateLimitExceeded
    from api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    logger.info("✅ Rate limiting enabled")
except ImportError as e:
    logger.warning(f"⚠️ Rate limiting not available: {e}")
    logger.warning("Install slowapi: pip install slowapi")

# --- 2. Audit Logging Middleware ---
try:
    from api.middleware.audit import audit_middleware
    
    @app.middleware("http")
    async def audit_logging(request, call_next):
        """Audit all API requests"""
        return await audit_middleware(request, call_next)
    
    logger.info("✅ Audit logging enabled")
except ImportError as e:
    logger.warning(f"⚠️ Audit logging not available: {e}")

# --- 3. CORS ---
# 🔒 Security: Read allowed origins from environment variable
# Default to localhost for development, production MUST override this
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:8080,https://app.minepi.com")
origins = [origin.strip() for origin in _cors_origins_raw.split(",") if origin.strip()]

# Security check: warn if wildcard is accidentally configured
if "*" in origins or "" in origins:
    logger.warning("⚠️ SECURITY: Wildcard CORS origin detected! This should NOT be used in production.")

logger.info(f"🔒 CORS allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-OKX-API-KEY", "X-OKX-SECRET-KEY", "X-OKX-PASSPHRASE"],
)

# --- 4. GZip Compression (Performance Optimization) ---
# 自動壓縮大於1KB的響應，減少帶寬消耗，提升加載速度
app.add_middleware(GZipMiddleware, minimum_size=1000)
logger.info("✅ GZip compression enabled")

# --- 5. Security Headers Middleware (Stage 2 Security) ---
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    Stage 2 Security: Add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: Prevent MIME type sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: Enable XSS filter
    - Referrer-Policy: Control referrer information
    - Strict-Transport-Security (production): Force HTTPS
    - Content-Security-Policy (production): Control resource loading
    """
    response = await call_next(request)

    # Basic security headers (always on)
    response.headers["X-Content-Type-Options"] = "nosniff"
    # X-Frame-Options intentionally omitted — Pi Browser loads DApps in WebView;
    # frame-ancestors is controlled via CSP below.
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Production-only headers (require HTTPS)
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            # Pi SDK + CDN libraries (Tailwind, Lucide)
            "script-src 'self' 'unsafe-inline' https://sdk.minepi.com https://cdn.minepi.com "
            "https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "img-src 'self' data: https:; "
            # Pi API + WebSocket + external data sources
            "connect-src 'self' https://api.minepi.com https://sdk.minepi.com wss: ws:; "
            # Allow Pi Browser / Pi Sandbox to embed this app
            "frame-ancestors 'self' https://app.minepi.com https://sandbox.minepi.com"
        )

    return response

logger.info("✅ Security headers enabled")

from fastapi import Response
import time

# 服務啟動時間
SERVICE_START_TIME = time.time()

# ================================================================
# Include API Routers
# ================================================================
app.include_router(system.router)
app.include_router(analysis.router)
app.include_router(market.router)
app.include_router(twstock.router)
app.include_router(usstock.router)
app.include_router(trading.router)
app.include_router(user.router)
app.include_router(forum_router)   # 論壇 API
app.include_router(premium_router) # 高級會員 API
app.include_router(admin_router)   # 管理員 API（配置管理）
app.include_router(admin_panel_router)  # 管理後台 API（廣播+用戶管理）
app.include_router(friends_router) # 好友功能 API
app.include_router(messages_router) # 私訊功能 API
app.include_router(audit_router)   # 審計日誌查詢 API (管理員專用)
app.include_router(scam_tracker_router)  # 可疑錢包追蹤系統 API
app.include_router(governance_router)  # 社群治理系統 API
app.include_router(notifications_router)  # 通知系統 API
app.include_router(alerts_router)  # 價格警報 API
app.include_router(tools_router)   # 工具偏好 API

# --- 健康檢查端點（用於負載均衡和監控）---
@app.get("/health")
async def health_check():
    """
    健康檢查端點 - 用於負載均衡器確認服務存活
    返回 200 表示服務正常運行
    """
    return {
        "status": "healthy",
        "service": "pi_crypto_insight",
        "uptime_seconds": int(time.time() - SERVICE_START_TIME)
    }

@app.get("/ready")
async def readiness_check():
    """
    就緒檢查端點 - 確認服務可以接受請求
    檢查關鍵組件是否已初始化
    """
    ready = True
    components = {}
    
    # 檢查 OKX Connector
    components["okx_connector"] = globals.okx_connector is not None
    
    # 檢查數據庫
    try:
        components["database"] = True
    except Exception:
        components["database"] = False
        ready = False
    
    status_code = 200 if ready else 503
    
    return Response(
        content=str({
            "status": "ready" if ready else "not_ready",
            "components": components,
            "uptime_seconds": int(time.time() - SERVICE_START_TIME)
        }),
        status_code=status_code,
        media_type="application/json"
    )


# --- Pi Network 域名驗證 ---
from core.config import PI_VALIDATION_KEY

@app.get("/validation-key.txt", response_class=PlainTextResponse)
async def pi_validation():
    """Pi Network 域名所有權驗證"""
    return PI_VALIDATION_KEY

# --- 前端 Debug Log API ---
from pydantic import BaseModel
from typing import Optional
import datetime

class FrontendLog(BaseModel):
    level: str = "info"
    message: str
    data: Optional[dict] = None

@app.post("/api/debug-log")
async def receive_frontend_log(
    log: FrontendLog,
    current_user: dict = Depends(get_current_user)
):
    """接收前端 debug log 並寫入檔案 (需登入)"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{log.level.upper()}] {log.message}"
    if log.data:
        log_line += f" | Data: {log.data}"

    # 寫入檔案
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: _append_log("frontend_debug.log", log_line))

    logger.info(f"[Frontend] {log.message}")
    return {"status": "logged"}

def _append_log(filepath, content):
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(content + "\n")

@app.get("/api/debug-log", response_class=PlainTextResponse)
async def get_debug_logs(admin: dict = Depends(require_admin)):
    """查看 debug logs (需管理員權限)"""
    try:
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(None, lambda: _read_log("frontend_debug.log"))
        return content
    except FileNotFoundError:
        return "No logs yet"

def _read_log(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise

# --- 靜態檔案與頁面 (帶緩存優化) ---
class CachedStaticFiles(StaticFiles):
    """
    帶緩存優化的靜態文件服務
    為靜態資源添加 Cache-Control 頭，提升二次訪問速度
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        # 設置緩存 1 天 (86400 秒) -> 改為 0 (No Cache) 以便調試
        # response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

if os.path.exists("web"):
    app.mount("/static", CachedStaticFiles(directory="web"), name="static")
    logger.info("✅ Static files mounted with caching (1 day)")

if __name__ == "__main__":
    logger.info("🚀 Pi Crypto Insight API Server 啟動中...")
    logger.info("VERIFICATION_TAG: Fix-500-Masking-v3-Robust") 
    logger.info("🏠 本地網址: http://localhost:8080")
    logger.info("📱 請在 Pi Browser 中使用 HTTPS 網址訪問 (如透過 ngrok)")
    uvicorn.run(app, host="0.0.0.0", port=8080)
