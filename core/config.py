import os
import sys
from dotenv import load_dotenv

# Fix Windows console encoding (cp950 cannot handle emoji/unicode)
if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load environment variables with override to ensure .env file values take precedence
load_dotenv(override=True)

# === 測試模式配置 ===
# 設為 True 時，跳過登入驗證，自動以測試用戶身份登入
# ⚠️ 安全警告：測試模式會繞過付費、認證等安全檢查
# ⚠️ 預設為 False（安全），開發時需明確設置 TEST_MODE=true
# 可透過環境變數 TEST_MODE=true 來啟用（僅限開發環境）
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# 🔒 Security: Multi-layer protection for TEST_MODE
if TEST_MODE:
    # Check 1: Environment must NOT be production
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env in ["production", "prod"]:
        raise ValueError(
            "🚨 SECURITY ALERT: TEST_MODE is ENABLED in a PRODUCTION environment!\n"
            "This is NOT allowed. TEST_MODE bypasses security checks.\n"
            "Please set TEST_MODE=false or remove it from environment variables."
        )

    # Check 2: Must explicitly confirm understanding of risks
    confirmation = os.getenv("TEST_MODE_CONFIRMATION", "")
    if confirmation != "I_UNDERSTAND_THE_RISKS":
        raise ValueError(
            "🚨 SECURITY ALERT: TEST_MODE requires explicit confirmation.\n"
            "To enable TEST_MODE in development, set:\n"
            "  TEST_MODE=true\n"
            "  TEST_MODE_CONFIRMATION=I_UNDERSTAND_THE_RISKS"
        )

    # Check 3: IP whitelist (optional but recommended)
    ip_whitelist = os.getenv("TEST_MODE_IP_WHITELIST", "")
    if ip_whitelist:
        # Simple format check (IP should have dots)
        if "." not in ip_whitelist:
            raise ValueError(
                "🚨 SECURITY ALERT: TEST_MODE_IP_WHITELIST must be a valid IP address.\n"
                "Example: TEST_MODE_IP_WHITELIST=127.0.0.1"
            )

    # All checks passed - log warning but allow
    import logging
    logging.warning("⚠️⚠️⚠️ TEST_MODE IS ENABLED - SECURITY CHECKS ARE BYPASSED ⚠️⚠️⚠️")

# 測試用戶資料（TEST_MODE=True 時使用）
TEST_USER = {
    "uid": "test-user-001",
    "username": "TestUser",
    "accessToken": "test-token-12345"
}

# === AI 模型配置 ===
# 所有模型名稱統一由 core/model_config.py 管理，在此不再硬寫字串。
from core.model_config import OPENAI_DEFAULT_MODEL, GEMINI_DEFAULT_MODEL

FAST_THINKING_MODEL = OPENAI_DEFAULT_MODEL   # 用於快速分析（分析師）
DEEP_THINKING_MODEL = OPENAI_DEFAULT_MODEL   # 用於深度思考（交易員、風險管理）

# ============================================================================
# [User-Side] 需要用戶 API Key 的功能
# ============================================================================

# 多頭研究員 (用戶付費)
BULL_RESEARCHER_MODEL = {
    "provider": "user_provided",
    "model": OPENAI_DEFAULT_MODEL,
}

# 空頭研究員 (用戶付費)
BEAR_RESEARCHER_MODEL = {
    "provider": "user_provided",
    "model": OPENAI_DEFAULT_MODEL,
}

# 交易員 (用戶付費)
TRADER_MODEL = {
    "provider": "user_provided",
    "model": OPENAI_DEFAULT_MODEL,
}

# 綜合模型 (用戶付費)
SYNTHESIS_MODEL = {
    "provider": "user_provided",
    "model": OPENAI_DEFAULT_MODEL,
}

# 查詢解析 (用戶付費)
QUERY_PARSER_MODEL_CONFIG = {
    "provider": "user_provided",
    "model": OPENAI_DEFAULT_MODEL,
}



# ============================================================================

# [Server-Side] 由平台提供的免費功能 (後台運行)

# ============================================================================



# 市場脈動分析器 (平台付費 - 用於生成公共報告)

MARKET_PULSE_MODEL = {
    "provider": "openai",  # 使用伺服器端的 .env KEY
    "model": OPENAI_DEFAULT_MODEL,
}



# 向後兼容：保留模型名稱字符串（供直接使用模型名稱的代碼使用）
QUERY_PARSER_MODEL = QUERY_PARSER_MODEL_CONFIG["model"]

# 支持的交易所列表，按優先級排序
SUPPORTED_EXCHANGES = ["okx"]

# 合約市場分析的默認槓桿
DEFAULT_FUTURES_LEVERAGE = 5

# 並行分析的最大工作線程數
MAX_ANALYSIS_WORKERS = 2

# Plan Reflection: max number of re-planning attempts allowed when reflection rejects the plan
PLAN_REFLECTION_MAX_RETRIES = 3

# Gradio 介面的預設值
DEFAULT_INTERVAL = "1d"
DEFAULT_KLINES_LIMIT = 200  # 業界標準：200 天，確保統計有效性

# 新聞抓取數量限制 (每個來源)
NEWS_FETCH_LIMIT = 10 # 每個來源嘗試抓取 10 條新聞

# 加密貨幣篩選器的預設值
SCREENER_DEFAULT_LIMIT = 30
SCREENER_DEFAULT_INTERVAL = "1d"

# === 自動篩選器/市場掃描配置 ===
# 指定要每天自動分析的重點幣種 (減少數量以提升效能，建議 3-5 個)
# 注意：僅包含 OKX 交易所實際存在的幣種
SCREENER_TARGET_SYMBOLS = ["BTC", "ETH", "SOL"]

# 自動更新間隔 (分鐘)
SCREENER_UPDATE_INTERVAL_MINUTES = int(os.getenv("SCREENER_UPDATE_INTERVAL_MINUTES", "5"))

# 資金費率自動更新間隔 (秒)
FUNDING_RATE_UPDATE_INTERVAL = int(os.getenv("FUNDING_RATE_UPDATE_INTERVAL", "300"))

# === 市場脈動 (Market Pulse) 配置 ===
# 固定監控的幣種列表 (優先級最高)
# 注意：僅包含 OKX 交易所實際存在的幣種
MARKET_PULSE_TARGETS = ["BTC", "ETH", "SOL"]

# 自動排名的幣種數量 (已停用 - 改為全市場掃描)
# MARKET_PULSE_BATCH_SIZE = 20

# 市場脈動更新頻率 (秒) - 4小時
MARKET_PULSE_UPDATE_INTERVAL = 14400

# === 交易限制配置 ===
MINIMUM_INVESTMENT_USD = 20.0  # 最低投資金額 (USDT)
MAXIMUM_INVESTMENT_USD = 30.0  # 最高投資金額 (USDT)
EXCHANGE_MINIMUM_ORDER_USD = 1.0  # 交易所最低下單金額 (USDT)

# === 交易類型選擇 ===
# 控制是否執行現貨交易和合約交易
# True: 啟用該類型的交易 / False: 停用該類型的交易
ENABLE_SPOT_TRADING = False      # 是否執行現貨交易
ENABLE_FUTURES_TRADING = True   # 是否執行合約交易

# === 加密貨幣分析配置 ===
# 預設要分析的加密貨幣列表。
# 用戶可以在此處修改此列表，以選擇要分析的加密貨幣。
CRYPTO_CURRENCIES_TO_ANALYZE = ["PIUSDT"]

# === OKX API 配置 ===
# 從 .env 檔案或環境變數讀取 OKX API 資訊
OKX_API_KEY = os.getenv("OKX_API_KEY", "")
OKX_API_SECRET = os.getenv("OKX_API_SECRET", "")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")

# 是否使用模擬盤 (Paper Trading)
# True: 使用模擬盤 / False: 使用真實帳戶
PAPER_TRADING = False

# === Pi Network 支付價格配置 ===
# 定義各種操作的 Pi 幣價格（用於後端驗證防止金額篡改）
PI_PAYMENT_PRICES = {
    "create_post": 1.0,    # 發文費用 1 Pi
    "tip": 1.0,            # 打賞 1 Pi
    "premium": 1.0,      # 高級會員 1 Pi
}

# === 論壇會員限制配置 ===
# None 表示無限制
FORUM_LIMITS = {
    "daily_post_free": 3,        # 一般會員每日發文上限
    "daily_post_premium": None,  # 高級會員每日發文上限 (None = 無限)
    "daily_comment_free": 20,    # 一般會員每日回覆上限
    "daily_comment_premium": None,  # 高級會員每日回覆上限 (None = 無限)
}
