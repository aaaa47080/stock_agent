
# === AI 模型配置 ===
# 基礎模型（用於分析師團隊）
FAST_THINKING_MODEL = "gpt-4o"  # 用於數據收集和快速分析
DEEP_THINKING_MODEL = "o4-mini"  # 用於深度推理和決策

# === 多模型辯論配置 ===
# 是否啟用多模型辯論（不同模型扮演多空雙方）
ENABLE_MULTI_MODEL_DEBATE = True

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

# === OpenRouter 配置 ===
# OpenRouter API 設定（如果使用 OpenRouter）
OPENROUTER_API_KEY = None  # 從環境變量讀取
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# OpenRouter 熱門模型推薦
OPENROUTER_MODELS = {
    # Anthropic Claude 系列
    "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
    "claude-3-opus": "anthropic/claude-3-opus",
    "claude-3-haiku": "anthropic/claude-3-haiku",

    # OpenAI 系列
    "gpt-4-turbo": "openai/gpt-4-turbo",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",

    # Google Gemini 系列
    "gemini-pro-1.5": "google/gemini-pro-1.5",
    "gemini-flash-1.5": "google/gemini-flash-1.5",

    # Meta Llama 系列
    "llama-3.1-70b": "meta-llama/llama-3.1-70b-instruct",
    "llama-3.1-405b": "meta-llama/llama-3.1-405b-instruct",

    # 其他優秀模型
    "qwen-2.5-72b": "qwen/qwen-2.5-72b-instruct",
    "deepseek-chat": "deepseek/deepseek-chat",
}

# === 推薦的辯論組合 ===
# 組合1: Claude vs GPT（經典對決）
# BULL: anthropic/claude-3.5-sonnet (保守穩健)
# BEAR: openai/gpt-4o (激進創新)

# 組合2: GPT vs Gemini（多樣性）
# BULL: openai/gpt-4o
# BEAR: google/gemini-pro-1.5

# 組合3: Claude vs Llama（開源vs商業）
# BULL: anthropic/claude-3.5-sonnet
# BEAR: meta-llama/llama-3.1-70b-instruct

# 組合4: 全開源
# BULL: qwen/qwen-2.5-72b-instruct
# BEAR: meta-llama/llama-3.1-70b-instruct
