import os
from dotenv import load_dotenv

# Load environment variables with override to ensure .env file values take precedence
load_dotenv(override=True)

# === AI 模型配置 ===
# 基礎模型（用於分析師團隊）
FAST_THINKING_MODEL = "gpt-4o"  # 用於數據收集和快速分析
DEEP_THINKING_MODEL = "o4-mini"  # 用於深度推理和決策

# === 多模型辯論配置 ===
# 是否啟用多模型辯論（不同模型扮演多空雙方）
ENABLE_MULTI_MODEL_DEBATE = True

# === 啟用委員會模式 ===
# False: 單一模型對單一模型 (多頭 1個 vs 空頭 1個)
# True:  委員會模式 (多頭多個 → 綜合 vs 空頭多個 → 綜合)
ENABLE_COMMITTEE_MODE = True  # 設為 True 啟用委員會模式

# ============================================================================
# 單一模型辯論配置 (ENABLE_COMMITTEE_MODE = False 時使用)
# ============================================================================

# 多頭研究員使用的模型
BULL_RESEARCHER_MODEL = {
    "provider": "openai",  # 選項: "openai" 或 "openrouter"
    "model": "gpt-4o",  # OpenAI 模型名稱
    # OpenRouter 範例:
    # "provider": "openrouter",
    # "model": "anthropic/claude-3.5-sonnet",
}

# 空頭研究員使用的模型
BEAR_RESEARCHER_MODEL = {
    "provider": "openai",  # 選項: "openai" 或 "openrouter"
    "model": "o4-mini",  # OpenAI 模型名稱
    # OpenRouter 範例:
    # "provider": "openrouter",
    # "model": "google/gemini-pro-1.5",
}

# 交易員使用的模型
TRADER_MODEL = {
    "provider": "openai",
    "model": "o4-mini",
}

# ============================================================================
# 委員會模式配置 (ENABLE_COMMITTEE_MODE = True 時使用)
# ============================================================================

# === 多頭委員會 ===
# 多個模型都給出多頭觀點，然後綜合
BULL_COMMITTEE_MODELS = [
    # {"provider": "openai", "model": "gpt-4.1-mini"},  
    # {"provider": "openai", "model": "gpt-5-mini"},                        # GPT-4o mini
    # {"provider": "google_gemini", "model": "gemini-3-flash-preview"},              # Gemini 2.5 Flash (最新穩定版)
    # {"provider": "openrouter", "model": "qwen/qwen3-235b-a22b:free"},        # Qwen 免費版
    {"provider": "local", "model": "/home/danny/AI-agent/Qwen3_4B_2507"},         # 本地模型 (vLLM/Ollama)
]

# === 空頭委員會 ===
# 多個模型都給出空頭觀點，然後綜合
BEAR_COMMITTEE_MODELS = [
    # {"provider": "openai", "model": "gpt-4.1-mini"},  
    # {"provider": "openai", "model": "gpt-5-mini"},                           # GPT-4o mini
    # {"provider": "google_gemini", "model": "gemini-3-flash-preview"},              # Gemini 2.5 Flash (最新穩定版)
    # {"provider": "openrouter", "model": "qwen/qwen3-235b-a22b:free"},        # Qwen 免費版
    {"provider": "local", "model": "/home/danny/AI-agent/Qwen3_4B_2507"},    # 本地模型 (vLLM/Ollama)
]

# === 綜合模型 ===
# 用於整合委員會意見的模型
SYNTHESIS_MODEL = {
    "provider": "local",
    "model": "/home/danny/AI-agent/Qwen3_4B_2507",
}

# === OpenRouter 配置 ===
# OpenRouter API 設定（如果使用 OpenRouter）
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# === Google Gemini 配置 ===
# Google Gemini API 設定（如果使用官方 Gemini API）
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# === 本地/落地模型配置 (Local LLM) ===
# 用於連接 vLLM, Ollama, LM Studio 等本地推理服務
LOCAL_LLM_CONFIG = {
    "base_url": "http://0.0.0.0:8080/v1",  # 本地 API 地址
    "api_key": "not-needed",               # 本地模型通常不需要 API Key
    "temperature": 0.1,                    # 預設溫度
    "seed": 42                             # 固定隨機種子 (可選)
}

# === 介面與應用程式配置 ===

# 用於解析用戶查詢的 LLM 模型
QUERY_PARSER_MODEL = "gpt-4o"

# 支持的交易所列表，按優先級排序
SUPPORTED_EXCHANGES = ["okx", "binance"]

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
