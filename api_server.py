import os
import sys
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# 將專案根目錄加入 Python 路徑
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import logging

# Load environment variables
load_dotenv()

# Configure Logging
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Create file handler
file_handler = logging.FileHandler("api_server.log", encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_formatter)

# Create console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[file_handler, console_handler]
)

# Import from refactored modules
from api.utils import logger
import api.globals as globals
from api.services import (
    load_screener_cache,
    load_market_pulse_cache,
    load_funding_rate_cache,
    update_screener_task,
    update_market_pulse_task,
    funding_rate_update_task
)
from api.routers import system, analysis, market, trading, user, agents

# Initialize database (ensure tables exist)
from core.database import init_db
init_db()
logger.info("✅ Database initialized")

# Core imports for initialization
try:
    from interfaces.chat_interface import CryptoAnalysisBot
    from trading.okx_api_connector import OKXAPIConnector
except ImportError as e:
    logger.critical(f"無法導入核心模組: {e}")
    sys.exit(1)

# Initialize Global Instances
try:
    globals.okx_connector = OKXAPIConnector()
    logger.info("OKX Connector 初始化成功")
except Exception as e:
    logger.error(f"OKX Connector 初始化失敗: {e}")
    globals.okx_connector = None

try:
    globals.bot = CryptoAnalysisBot()
    logger.info("CryptoAnalysisBot 初始化成功")
except Exception as e:
    logger.error(f"CryptoAnalysisBot 初始化失敗: {e}")
    globals.bot = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 嘗試載入快取
    load_screener_cache()
    load_market_pulse_cache()
    load_funding_rate_cache()

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
    yield
    # Shutdown logic can go here if needed

app = FastAPI(title="Crypto Trading System API", version="1.1.0", lifespan=lifespan)

# --- 安全性強化: CORS ---
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "https://app.minepi.com", # Pi Browser 環境
    "*", # 開發階段允許所有，生產環境請限制
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(system.router)
app.include_router(analysis.router)
app.include_router(market.router)
app.include_router(trading.router)
app.include_router(user.router)
app.include_router(agents.router)  # Agent 管理 API

# --- 靜態檔案與頁面 ---
if os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")

if __name__ == "__main__":
    logger.info("🚀 Pi Crypto Insight API Server 啟動中...")
    logger.info(f"🏠 本地網址: http://localhost:8111")
    logger.info("📱 請在 Pi Browser 中使用 HTTPS 網址訪問 (如透過 ngrok)")
    uvicorn.run(app, host="0.0.0.0", port=8111)
