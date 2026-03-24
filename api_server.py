# ruff: noqa: E402
# ^ E402 ignored because we need to modify sys.path before importing local modules
import asyncio
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

# Fix Windows console encoding (cp950 cannot handle emoji/unicode)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 將專案根目錄加入 Python 路徑
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

from config.logging_config import setup_json_logging

app_log_level_name = os.getenv("APP_LOG_LEVEL", "WARNING").upper()
app_log_level = getattr(logging, app_log_level_name, logging.WARNING)

use_json_logging = os.getenv("LOG_FORMAT", "text").lower() == "json"

if use_json_logging:
    setup_json_logging(app_log_level)
else:
    log_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(app_log_level)
    console_handler.setFormatter(log_formatter)
    logging.basicConfig(
        level=app_log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[console_handler],
    )


# 靜音 Windows asyncio WinError 10054（客戶端斷線時的無害噪音）
class _SuppressWinError10054(logging.Filter):
    def filter(self, record):
        return "WinError 10054" not in (record.getMessage())


logging.getLogger("asyncio").addFilter(_SuppressWinError10054())

# Import from refactored modules
from api.deps import get_current_user, require_admin
from api.health import router as health_router
from api.lifespan import lifespan
from api.middleware_setup import setup_middleware
from api.routers import (
    analysis,
    commodity,
    forex,
    market,
    system,
    twstock,
    user,
    usstock,
)
from api.routers.admin import router as admin_router
from api.routers.alerts import router as alerts_router  # Price Alerts API
from api.routers.audit import router as audit_router  # Audit log admin API
from api.routers.forum import router as forum_router
from api.routers.friends import router as friends_router
from api.routers.governance import (
    router as governance_router,  # Community governance API
)
from api.routers.messages import router as messages_router
from api.routers.notifications import (
    router as notifications_router,  # Notifications API
)
from api.routers.premium import router as premium_router
from api.routers.scam_tracker import router as scam_tracker_router  # Scam tracker API
from api.routers.tools import router as tools_router  # Tool preferences API
from api.utils import logger

# --- 創建 FastAPI 應用 ---
app = FastAPI(title="Crypto Trading System API", version="1.2.0", lifespan=lifespan)

# --- 註冊 Middleware ---
setup_middleware(app)

# ================================================================
# Include API Routers
# ================================================================
app.include_router(system.router)
app.include_router(analysis.router)
app.include_router(market.router)
app.include_router(twstock.router)
app.include_router(usstock.router)
app.include_router(commodity.router)
app.include_router(forex.router)
app.include_router(user.router)
app.include_router(health_router)  # Health check endpoints
app.include_router(forum_router)  # 論壇 API
app.include_router(premium_router)  # 高級會員 API
app.include_router(admin_router)  # 管理員/後台 API
app.include_router(friends_router)  # 好友功能 API
app.include_router(messages_router)  # 私訊功能 API
app.include_router(audit_router)  # 審計日誌查詢 API (管理員專用)
app.include_router(scam_tracker_router)  # 可疑錢包追蹤系統 API
app.include_router(governance_router)  # 社群治理系統 API
app.include_router(notifications_router)  # 通知系統 API
app.include_router(alerts_router)  # 價格警報 API
app.include_router(tools_router)  # 工具偏好 API


# --- Pi Network 域名驗證 ---
from core.config import PI_VALIDATION_KEY


@app.get("/validation-key.txt", response_class=PlainTextResponse)
async def pi_validation():
    """Pi Network 域名所有權驗證"""
    return PI_VALIDATION_KEY


# --- 前端 Debug Log API ---
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from pydantic import BaseModel, Field

_frontend_logger = logging.getLogger("frontend_debug")
_frontend_logger.setLevel(logging.INFO)
if not _frontend_logger.handlers:
    _rotating_handler = RotatingFileHandler(
        "frontend_debug.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _rotating_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    _frontend_logger.addHandler(_rotating_handler)


class FrontendLog(BaseModel):
    level: str = "info"
    message: str = Field(max_length=2000)
    data: Optional[dict] = None


@app.post("/api/debug-log")
async def receive_frontend_log(
    log: FrontendLog, current_user: dict = Depends(get_current_user)
):
    """接收前端 debug log 並寫入檔案 (需登入)"""
    log_func = getattr(_frontend_logger, log.level.lower(), _frontend_logger.info)
    log_line = log.message
    if log.data:
        log_line += f" | Data: {log.data}"
    log_func(log_line)
    return {"status": "logged"}


@app.get("/api/debug-log", response_class=PlainTextResponse)
async def get_debug_logs(admin: dict = Depends(require_admin)):
    """查看 debug logs (需管理員權限) — 僅讀取最後 100KB"""
    try:

        def _read_log():
            import os

            size = os.path.getsize("frontend_debug.log")
            with open("frontend_debug.log", "r", encoding="utf-8") as f:
                if size > 100 * 1024:
                    f.seek(max(0, size - 100 * 1024))
                    return "... (truncated) ...\n" + f.read()
                return f.read()

        return await asyncio.get_running_loop().run_in_executor(None, _read_log)
    except FileNotFoundError:
        return "No logs yet"


# --- 靜態檔案與頁面 ---
if os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")
    for sub in ("js", "css", "img", "assets"):
        sub_dir = os.path.join("web", sub)
        if os.path.isdir(sub_dir):
            app.mount(f"/{sub}", StaticFiles(directory=sub_dir), name=sub)
    logger.info("Static files mounted (no-cache via security middleware)")

if __name__ == "__main__":
    logger.info("🚀 Pi Crypto Insight API Server 啟動中...")
    logger.info("VERIFICATION_TAG: Fix-500-Masking-v3-Robust")
    logger.info("🏠 本地網址: http://localhost:8080")
    logger.info("📱 請在 Pi Browser 中使用 HTTPS 網址訪問 (如透過 ngrok)")
    workers = int(os.getenv("WEB_CONCURRENCY", "1"))

    # Uvicorn requires an import string when using multiple workers or reload.
    if workers > 1:
        logger.info(
            f"👷 Using WEB_CONCURRENCY={workers}, starting with import string mode"
        )
        uvicorn.run("api_server:app", host="0.0.0.0", port=8080, workers=workers)
    else:
        uvicorn.run(app, host="0.0.0.0", port=8080)
