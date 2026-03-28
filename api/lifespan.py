"""Lifespan event handlers — startup and shutdown logic for the FastAPI app."""

import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

import api.globals as globals
from api.alert_checker import price_alert_check_task
from api.services import (
    funding_rate_update_task,
    load_market_pulse_cache,
    update_market_pulse_task,
    update_screener_task,
)
from api.utils import logger
from core.db_ready import mark_db_failed, mark_db_ready, reset_db_ready_state
from core.database import init_db
from utils.okx_api_connector import OKXAPIConnector


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    startup_t0 = time.perf_counter()

    def _startup_mark(step: str, status: str = "ok"):
        elapsed_ms = int((time.perf_counter() - startup_t0) * 1000)
        logger.info(f"🚦 STARTUP[{status}] +{elapsed_ms}ms | {step}")

    _startup_mark("lifespan_enter")
    reset_db_ready_state()

    async def _init_database_background():
        """Run DB initialization in background to avoid blocking readiness on startup."""
        skip_db_init = os.getenv("SKIP_DB_INIT", "false").lower() == "true"
        if skip_db_init:
            logger.info("⏭️ 跳過資料庫初始化 (SKIP_DB_INIT=true)")
            mark_db_ready()
            return

        logger.info("🔄 Initializing database in background...")
        loop = asyncio.get_running_loop()
        try:
            # init_db 內部已有重試機制（10次，每次間隔3秒）
            await loop.run_in_executor(None, init_db)
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"⚠️ 資料庫初始化失敗: {e}")
            logger.warning("⏭️ 應用程式將繼續運行，部分功能可能無法使用")
            mark_db_failed(e)
            return

        # ORM migration: run Alembic upgrade to head
        try:
            from alembic.config import Config

            from alembic import command

            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            logger.info("ORM Alembic migration complete (head)")
        except Exception as e:
            logger.warning("ORM Alembic migration skipped: %s", e)

        # Seed tools catalog (idempotent — skips existing rows)
        try:
            from core.database.tools import seed_tools_catalog

            await loop.run_in_executor(None, seed_tools_catalog)
            logger.info("✅ Tools catalog seeded")
        except Exception as e:
            logger.warning(f"⚠️ Tools catalog seeding failed: {e}")

        mark_db_ready()

    # 不阻塞 startup，避免被平台 readiness probe 提前判斷失敗
    asyncio.create_task(_init_database_background())
    _startup_mark("db_init_background_scheduled")

    from core.config import TEST_MODE

    if TEST_MODE:
        logger.warning(
            "⚠️⚠️⚠️ TEST_MODE IS ENABLED! THIS SHOULD NOT BE ON IN PRODUCTION! ⚠️⚠️⚠️"
        )
        logger.warning("Test-only endpoints (e.g., /dev-login) are active.")

    # Startup: Initialize Global Instances
    try:
        globals.okx_connector = OKXAPIConnector()
        logger.info("✅ OKX Connector 初始化成功")
        _startup_mark("okx_connector_ready")
    except Exception as e:
        logger.error(f"❌ OKX Connector 初始化失敗: {e}")
        globals.okx_connector = None
        _startup_mark("okx_connector_failed", status="warn")

    # 預熱 V4 bootstrap（純載入 PromptRegistry + AgentRegistry，不建立 LLM）
    # 實際 LLM client 由各請求的使用者設定決定，所以 startup 僅驗證模組可 import
    try:
        from core.agents.bootstrap import bootstrap as _v4_bootstrap  # noqa: F401

        logger.info("✅ V4 ManagerAgent 模組載入成功（LLM 將在首次請求時初始化）")
        _startup_mark("v4_manager_module_loaded")
    except Exception as e:
        logger.warning(f"⚠️ V4 ManagerAgent 模組載入失敗（將 fallback 至 V1 bot）: {e}")
        _startup_mark("v4_manager_module_failed", status="warn")

    globals.v4_manager = None  # 實際 manager 按需在 analysis.py 中建立

    # Startup: 嘗試載入快取
    # [Optimization] Screener/Funding are now In-Memory Only, no DB load needed
    load_market_pulse_cache()  # Market Pulse remains persistent (slow updates)
    _startup_mark("market_pulse_cache_loaded")

    # Startup: 啟動背景篩選器更新任務
    asyncio.create_task(update_screener_task())
    _startup_mark("screener_task_scheduled")

    # Market Pulse 任務：檢查是否由獨立 Worker 處理
    # 設置環境變數 MARKET_PULSE_WORKER=1 時，API 不啟動此任務（由獨立 Worker 處理）
    if not os.getenv("MARKET_PULSE_WORKER"):
        logger.info("📊 Starting Market Pulse task in API process...")
        asyncio.create_task(update_market_pulse_task())
        _startup_mark("market_pulse_task_scheduled")
    else:
        logger.info(
            "📊 Market Pulse handled by external worker (MARKET_PULSE_WORKER=1)"
        )
        _startup_mark("market_pulse_task_external")

    # Startup: 啟動 Funding Rate 定期更新任務
    asyncio.create_task(funding_rate_update_task())
    _startup_mark("funding_rate_task_scheduled")

    # Startup: 啟動價格警報檢查任務
    asyncio.create_task(price_alert_check_task())
    logger.info("Price alert checker task started")
    _startup_mark("price_alert_task_scheduled")

    # Startup: 啟動審計日誌清理任務 (Stage 2 Security)
    # 每天凌晨 3 點自動清理超過 90 天的舊日誌
    try:
        from core.audit import audit_log_cleanup_task

        asyncio.create_task(audit_log_cleanup_task())
        logger.info("✅ Audit log cleanup task scheduled (daily at 3 AM UTC)")
        _startup_mark("audit_cleanup_task_scheduled")
    except ImportError:
        logger.warning("⚠️ Audit log cleanup task not available")
        _startup_mark("audit_cleanup_task_unavailable", status="warn")

    # Startup: JWT 密鑰輪換 (Stage 3 Security)
    # 先等 DB ready 並同步初始化 key manager，再 yield 開始接收請求，
    # 徹底消除 RuntimeError race condition。
    if os.getenv("USE_KEY_ROTATION", "false").lower() == "true":
        try:
            from core.key_rotation import get_key_manager, key_rotation_task

            _km = get_key_manager()
            if not _km._initialized:
                logger.info("🔑 Waiting for DB to initialize JWT key manager before accepting requests...")
                await wait_for_db_ready(timeout=30.0)
                await _km.initialize()
                logger.info("✅ JWT key manager initialized (startup-blocking)")
                _startup_mark("jwt_key_manager_initialized")

            # Background task handles hourly rotation checks (skips init since already done)
            asyncio.create_task(key_rotation_task())
            logger.info("✅ JWT key rotation task scheduled (hourly checks)")
            _startup_mark("jwt_rotation_task_scheduled")
        except Exception as e:
            logger.warning(f"⚠️ JWT key manager startup init failed: {e}, will retry in background")
            try:
                from core.key_rotation import key_rotation_task
                asyncio.create_task(key_rotation_task())
            except Exception:
                pass
            _startup_mark("jwt_rotation_task_fallback", status="warn")

    _startup_mark("startup_ready")

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

    # ORM: Close async engine
    try:
        from core.orm.session import close_async_engine

        await close_async_engine()
        logger.info("✅ ORM async engine closed")
    except Exception as e:
        logger.error(f"❌ 關閉 ORM async engine 時出錯: {e}")
