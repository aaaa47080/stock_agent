"""
簡化的多模型配置
使用簡潔的 "provider:model" 格式
"""

# ============================================================================
# 基礎配置
# ============================================================================

# === 啟用多模型辯論 ===
ENABLE_MULTI_MODEL_DEBATE = True

# === 啟用委員會模式 ===
# False: 單一模型對單一模型 (多頭 1個 vs 空頭 1個)
# True:  委員會模式 (多頭多個 → 綜合 vs 空頭多個 → 綜合)
ENABLE_COMMITTEE_MODE = True  # ✅ 啟用委員會模式

# ============================================================================
# 單一模型辯論配置 (ENABLE_COMMITTEE_MODE = False 時使用)
# ============================================================================

# 格式: "provider:model"
# - openai:模型名         → 使用 OpenAI 官方 API
# - openrouter:模型全名   → 使用 OpenRouter API

# 多頭研究員模型
BULL_MODEL = "openai:gpt-4o"
# 其他選項:
# "openai:o4-mini"
# "openrouter:anthropic/claude-3.5-sonnet"
# "openrouter:google/gemini-pro-1.5"

# 空頭研究員模型
BEAR_MODEL = "openai:o4-mini"
# 其他選項:
# "openai:gpt-4o"
# "openrouter:anthropic/claude-3.5-sonnet"
# "openrouter:meta-llama/llama-3.1-70b-instruct"

# 交易員模型
TRADER_MODEL = "openai:o4-mini"

# ============================================================================
# 委員會模式配置 (ENABLE_COMMITTEE_MODE = True 時使用)
# ============================================================================

# === 多頭委員會 ===
# 多個模型都給出多頭觀點，然後綜合
BULL_COMMITTEE_MODELS = [
    "openai:gpt-5-mini",                             # GPT-4o 多頭專家
    "openrouter:google/gemma-3-27b-it:free",     # Claude 多頭專家（穩定）
]

# === 空頭委員會 ===
# 多個模型都給出空頭觀點，然後綜合
BEAR_COMMITTEE_MODELS = [
    "openai:gpt-5-mini",                                     # o4-mini 空頭專家
    "openrouter:google/gemma-3-27b-it:free",       # Llama 空頭專家（穩定）
]

# === 綜合模型 ===
# 用於整合委員會意見的模型
SYNTHESIS_MODEL = "openai:gpt-4o"

# ============================================================================
# 推薦配置範例
# ============================================================================

# === 範例 1: OpenAI 官方模型（最簡單） ===
"""
ENABLE_COMMITTEE_MODE = False
BULL_MODEL = "openai:gpt-4o"
BEAR_MODEL = "openai:o4-mini"
"""

# === 範例 2: 混合使用 OpenAI + OpenRouter ===
"""
ENABLE_COMMITTEE_MODE = False
BULL_MODEL = "openai:gpt-4o"
BEAR_MODEL = "openrouter:anthropic/claude-3.5-sonnet"
"""

# === 範例 3: 全部使用 OpenRouter（訪問所有模型） ===
"""
ENABLE_COMMITTEE_MODE = False
BULL_MODEL = "openrouter:anthropic/claude-3.5-sonnet"
BEAR_MODEL = "openrouter:google/gemini-pro-1.5"
"""

# === 範例 4: 委員會模式 - 三大商業模型 ===
"""
ENABLE_COMMITTEE_MODE = True
BULL_COMMITTEE_MODELS = [
    "openai:gpt-4o",
    "openrouter:anthropic/claude-3.5-sonnet",
    "openrouter:google/gemini-pro-1.5",
]
BEAR_COMMITTEE_MODELS = [
    "openai:o4-mini",
    "openrouter:anthropic/claude-3-opus",
    "openrouter:google/gemini-flash-1.5",
]
SYNTHESIS_MODEL = "openai:gpt-4o"
"""

# === 範例 5: 委員會模式 - 全開源（經濟） ===
"""
ENABLE_COMMITTEE_MODE = True
BULL_COMMITTEE_MODELS = [
    "openrouter:meta-llama/llama-3.1-70b-instruct",
    "openrouter:qwen/qwen-2.5-72b-instruct",
    "openrouter:deepseek/deepseek-chat",
]
BEAR_COMMITTEE_MODELS = [
    "openrouter:meta-llama/llama-3.1-70b-instruct",
    "openrouter:qwen/qwen-2.5-72b-instruct",
    "openrouter:deepseek/deepseek-chat",
]
SYNTHESIS_MODEL = "openrouter:meta-llama/llama-3.1-70b-instruct"
"""

# ============================================================================
# 可用模型快速參考
# ============================================================================

"""
=== OpenAI 官方模型 ===
openai:gpt-4o           # 最新多模態，推薦
openai:gpt-4o-mini      # 經濟版
openai:o4-mini          # 深度推理
openai:gpt-4-turbo      # 穩定經典

=== Claude 系列 (via OpenRouter) ===
openrouter:anthropic/claude-3.5-sonnet    # 最新，分析深入 ⭐
openrouter:anthropic/claude-3-opus        # 最強，但較貴
openrouter:anthropic/claude-3-haiku       # 快速，經濟

=== Gemini 系列 (via OpenRouter) ===
openrouter:google/gemini-pro-1.5          # 長上下文 ⭐
openrouter:google/gemini-flash-1.5        # 快速響應

=== Llama 系列 (via OpenRouter) ===
openrouter:meta-llama/llama-3.1-405b-instruct    # 最大開源模型
openrouter:meta-llama/llama-3.1-70b-instruct     # 平衡性能成本 ⭐

=== 中國開源模型 (via OpenRouter) ===
openrouter:qwen/qwen-2.5-72b-instruct     # 通義千問 ⭐
openrouter:deepseek/deepseek-chat         # DeepSeek，數學強
"""

# ============================================================================
# 成本參考
# ============================================================================

"""
高成本（質量最高）:
- openai:gpt-4o
- openrouter:anthropic/claude-3-opus
- openrouter:google/gemini-pro-1.5

中成本（平衡）:
- openai:gpt-4o-mini
- openrouter:anthropic/claude-3.5-sonnet
- openrouter:meta-llama/llama-3.1-70b-instruct

低成本（經濟）:
- openrouter:qwen/qwen-2.5-72b-instruct
- openrouter:deepseek/deepseek-chat
- openrouter:meta-llama/llama-3.1-70b-instruct

委員會模式成本 = 委員會成員數量 × 單次成本 + 綜合成本
例如: 3個成員 + 1個綜合 = 4次API調用
"""

# ============================================================================
# 配置建議
# ============================================================================

"""
日常分析（高頻）:
BULL_MODEL = "openai:gpt-4o-mini"
BEAR_MODEL = "openai:gpt-4o-mini"
→ 成本低，速度快

重要決策（低頻）:
BULL_MODEL = "openai:gpt-4o"
BEAR_MODEL = "openrouter:anthropic/claude-3.5-sonnet"
→ 質量高，多樣性好

極致質量（重大決策）:
ENABLE_COMMITTEE_MODE = True
BULL_COMMITTEE_MODELS = [
    "openai:gpt-4o",
    "openrouter:anthropic/claude-3.5-sonnet",
    "openrouter:google/gemini-pro-1.5",
]
→ 多個專家，可信度最高
"""
