"""
多模型委員會辯論配置
讓多個模型分別給出意見，然後綜合成最終論證
"""

# === 委員會模式配置 ===
# 是否啟用委員會模式（多個模型給出同一方觀點後綜合）
ENABLE_COMMITTEE_MODE = False  # 設為 True 啟用

# === 多頭委員會 (Bull Committee) ===
# 多個模型都扮演多頭，然後綜合觀點
BULL_COMMITTEE = [
    {
        "provider": "openai",
        "model": "gpt-4o",
        "name": "GPT-4o 多頭專家"
    },
    {
        "provider": "openrouter",
        "model": "anthropic/claude-3.5-sonnet",
        "name": "Claude 多頭專家"
    },
    {
        "provider": "openrouter",
        "model": "google/gemini-pro-1.5",
        "name": "Gemini 多頭專家"
    },
]

# === 空頭委員會 (Bear Committee) ===
# 多個模型都扮演空頭，然後綜合觀點
BEAR_COMMITTEE = [
    {
        "provider": "openai",
        "model": "o4-mini",
        "name": "o4-mini 空頭專家"
    },
    {
        "provider": "openrouter",
        "model": "meta-llama/llama-3.1-70b-instruct",
        "name": "Llama 空頭專家"
    },
    {
        "provider": "openrouter",
        "model": "qwen/qwen-2.5-72b-instruct",
        "name": "Qwen 空頭專家"
    },
]

# === 綜合模型 (用於整合委員會意見) ===
SYNTHESIS_MODEL = {
    "provider": "openai",
    "model": "gpt-4o",
}

# === 推薦的委員會組合 ===

# 組合1: 三大商業模型 (質量最高)
BULL_COMMITTEE_PREMIUM = [
    {"provider": "openai", "model": "gpt-4o", "name": "GPT-4o"},
    {"provider": "openrouter", "model": "anthropic/claude-3.5-sonnet", "name": "Claude"},
    {"provider": "openrouter", "model": "google/gemini-pro-1.5", "name": "Gemini"},
]

BEAR_COMMITTEE_PREMIUM = [
    {"provider": "openai", "model": "o4-mini", "name": "o4-mini"},
    {"provider": "openrouter", "model": "anthropic/claude-3-opus", "name": "Claude Opus"},
    {"provider": "openrouter", "model": "google/gemini-flash-1.5", "name": "Gemini Flash"},
]

# 組合2: 平衡組合 (成本適中)
BULL_COMMITTEE_BALANCED = [
    {"provider": "openai", "model": "gpt-4o-mini", "name": "GPT-4o-mini"},
    {"provider": "openrouter", "model": "anthropic/claude-3-haiku", "name": "Claude Haiku"},
    {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct", "name": "Qwen"},
]

BEAR_COMMITTEE_BALANCED = [
    {"provider": "openai", "model": "gpt-4o-mini", "name": "GPT-4o-mini"},
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-70b-instruct", "name": "Llama"},
    {"provider": "openrouter", "model": "deepseek/deepseek-chat", "name": "DeepSeek"},
]

# 組合3: 全開源 (最經濟)
BULL_COMMITTEE_OPENSOURCE = [
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 70B"},
    {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 72B"},
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-405b-instruct", "name": "Llama 405B"},
]

BEAR_COMMITTEE_OPENSOURCE = [
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 70B"},
    {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 72B"},
    {"provider": "openrouter", "model": "deepseek/deepseek-chat", "name": "DeepSeek"},
]

# === 委員會模式說明 ===
"""
委員會模式的優勢:
1. 減少單一模型的偏見
2. 綜合多個"專家"的意見
3. 提高論證的可靠性
4. 發現更多角度和盲點

工作流程:
1. 多頭委員會的每個模型分別給出看漲論點
2. 綜合模型整合所有多頭論點 → 最終多頭論證
3. 空頭委員會的每個模型分別給出看跌論點
4. 綜合模型整合所有空頭論點 → 最終空頭論證
5. 最終多頭論證 vs 最終空頭論證 → 交易員決策

成本考慮:
- 委員會模式會調用更多模型，成本較高
- 建議在重要決策時使用
- 日常分析可以關閉委員會模式
"""
