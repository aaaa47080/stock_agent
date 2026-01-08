import os
from dotenv import load_dotenv

# Load environment variables with override to ensure .env file values take precedence
load_dotenv(override=True)

# === AI 模型配置 ===

# 基礎模型（用於分析師團隊 - 需用戶 Key）

FAST_THINKING_MODEL = "gpt-4o-mini"

DEEP_THINKING_MODEL = "gpt-4o-mini"



# === 多模型辯論配置 ===

ENABLE_MULTI_MODEL_DEBATE = True

ENABLE_COMMITTEE_MODE = True



# ============================================================================

# [User-Side] 需要用戶 API Key 的功能

# ============================================================================



# 多頭研究員 (用戶付費)

BULL_RESEARCHER_MODEL = {

    "provider": "user_provided", 

    "model": "gpt-4o-mini",

}



# 空頭研究員 (用戶付費)

BEAR_RESEARCHER_MODEL = {

    "provider": "user_provided",

    "model": "gpt-4o-mini",

}



# 交易員 (用戶付費)

TRADER_MODEL = {

    "provider": "user_provided",

    "model": "gpt-4o-mini",

}



# 裁判 (用戶付費)

JUDGE_MODEL = {

    "provider": "user_provided",

    "model": "gpt-4o-mini",

}



# 委員會成員 (用戶付費)

BULL_COMMITTEE_MODELS = [

    {"provider": "user_provided", "model": "gpt-4o-mini"},  

    {"provider": "user_provided", "model": "gpt-4o-mini"},

]



BEAR_COMMITTEE_MODELS = [

    {"provider": "user_provided", "model": "gpt-4o-mini"},  

    {"provider": "user_provided", "model": "gpt-4o-mini"},

]



# 綜合模型 (用戶付費)

SYNTHESIS_MODEL = {

    "provider": "user_provided",

    "model": "gpt-4o-mini",

}



# 查詢解析 (用戶付費)

QUERY_PARSER_MODEL_CONFIG = {

    "provider": "user_provided",

    "model": "gpt-4o-mini",

}



# ============================================================================

# [Server-Side] 由平台提供的免費功能 (後台運行)

# ============================================================================



# 市場脈動分析器 (平台付費 - 用於生成公共報告)

MARKET_PULSE_MODEL = {

    "provider": "openai", # 使用伺服器端的 .env KEY

    "model": "gpt-4o-mini",

}



# 向後兼容：保留模型名稱字符串（供直接使用模型名稱的代碼使用）
QUERY_PARSER_MODEL = QUERY_PARSER_MODEL_CONFIG["model"]

# 支持的交易所列表，按優先級排序
SUPPORTED_EXCHANGES = ["okx"]

# 合約市場分析的默認槓桿
DEFAULT_FUTURES_LEVERAGE = 5

# 並行分析的最大工作線程數
MAX_ANALYSIS_WORKERS = 2

# Gradio 介面的預設值
DEFAULT_INTERVAL = "1d"
DEFAULT_KLINES_LIMIT = 100

# 新聞抓取數量限制 (每個來源)
NEWS_FETCH_LIMIT = 10 # 每個來源嘗試抓取 10 條新聞

# 加密貨幣篩選器的預設值
SCREENER_DEFAULT_LIMIT = 30
SCREENER_DEFAULT_INTERVAL = "1d"

# === 自動篩選器/市場掃描配置 ===
# 指定要每天自動分析的重點幣種 (減少數量以提升效能，建議 3-5 個)
SCREENER_TARGET_SYMBOLS = ["BTC", "ETH", "SOL", "PI"]

# 自動更新間隔 (分鐘)
SCREENER_UPDATE_INTERVAL_MINUTES = 0.25

# 資金費率自動更新間隔 (秒)
FUNDING_RATE_UPDATE_INTERVAL = 60  # 1分鐘更新一次 (加速更新)

# === 市場脈動 (Market Pulse) 配置 ===
# 固定監控的幣種列表 (優先級最高)
MARKET_PULSE_TARGETS = ["BTC", "ETH", "SOL", "PI"]

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
