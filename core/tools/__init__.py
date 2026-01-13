"""
加密貨幣分析 LangChain 工具集
將現有分析功能封裝為 @tool，供 ReAct Agent 調用

此模組提供向後兼容的導出接口，原有的 import 路徑仍可正常使用。
"""

from typing import List

# 導入所有 Schema
from .schemas import (
    TechnicalAnalysisInput,
    NewsAnalysisInput,
    FullInvestmentAnalysisInput,
    PriceInput,
    CurrentTimeInput,
    MarketPulseInput,
    BacktestStrategyInput,
    ExtractCryptoSymbolsInput
)

# 導入輔助函數
from .helpers import (
    normalize_symbol,
    find_available_exchange,
    extract_crypto_symbols,
    CRYPTO_SYMBOLS,
    COMMON_WORDS
)

# 為了向後兼容，提供帶下劃線前綴的別名
_normalize_symbol = normalize_symbol
_find_available_exchange = find_available_exchange

# 導入格式化函數
from .formatters import format_full_analysis_result

# 導入所有工具
from .utility_tools import get_current_time_tool
from .crypto_tools import (
    technical_analysis_tool,
    news_analysis_tool,
    full_investment_analysis_tool,
    get_crypto_price_tool,
    explain_market_movement_tool,
    backtest_strategy_tool,
    extract_crypto_symbols_tool
)


# ============================================================================
# 工具列表導出
# ============================================================================

def get_crypto_tools() -> List:
    """獲取所有加密貨幣分析工具"""
    return [
        get_current_time_tool,
        get_crypto_price_tool,
        technical_analysis_tool,
        news_analysis_tool,
        full_investment_analysis_tool,
        explain_market_movement_tool,
        backtest_strategy_tool,
        extract_crypto_symbols_tool,
    ]


# ============================================================================
# 工具名稱映射（用於 Agent Registry）
# ============================================================================

TOOL_MAP = {
    "get_current_time_tool": get_current_time_tool,
    "get_crypto_price_tool": get_crypto_price_tool,
    "technical_analysis_tool": technical_analysis_tool,
    "news_analysis_tool": news_analysis_tool,
    "full_investment_analysis_tool": full_investment_analysis_tool,
    "explain_market_movement_tool": explain_market_movement_tool,
    "backtest_strategy_tool": backtest_strategy_tool,
    "extract_crypto_symbols_tool": extract_crypto_symbols_tool,
}


def get_tools_by_names(tool_names: List[str]) -> List:
    """
    根據工具名稱列表獲取工具對象

    Args:
        tool_names: 工具名稱列表，如 ["get_crypto_price_tool", "technical_analysis_tool"]

    Returns:
        對應的工具對象列表

    Example:
        tools = get_tools_by_names(["get_crypto_price_tool", "news_analysis_tool"])
    """
    return [TOOL_MAP[name] for name in tool_names if name in TOOL_MAP]


def get_available_tool_names() -> List[str]:
    """
    獲取所有可用工具的名稱列表

    Returns:
        工具名稱列表
    """
    return list(TOOL_MAP.keys())


def get_tool_by_name(tool_name: str):
    """
    根據名稱獲取單個工具對象

    Args:
        tool_name: 工具名稱

    Returns:
        工具對象或 None
    """
    return TOOL_MAP.get(tool_name)


# ============================================================================
# 向後兼容：保持原有的 __all__ 導出
# ============================================================================

__all__ = [
    # Schemas
    'TechnicalAnalysisInput',
    'NewsAnalysisInput',
    'FullInvestmentAnalysisInput',
    'PriceInput',
    'CurrentTimeInput',
    'MarketPulseInput',
    'BacktestStrategyInput',
    'ExtractCryptoSymbolsInput',
    # Helpers
    'normalize_symbol',
    'find_available_exchange',
    'extract_crypto_symbols',
    '_normalize_symbol',  # 向後兼容
    '_find_available_exchange',  # 向後兼容
    # Formatters
    'format_full_analysis_result',
    # Tools
    'get_current_time_tool',
    'get_crypto_price_tool',
    'technical_analysis_tool',
    'news_analysis_tool',
    'full_investment_analysis_tool',
    'explain_market_movement_tool',
    'backtest_strategy_tool',
    'extract_crypto_symbols_tool',
    # Tool management
    'get_crypto_tools',
    'get_tools_by_names',
    'get_available_tool_names',
    'get_tool_by_name',
    'TOOL_MAP',
]
