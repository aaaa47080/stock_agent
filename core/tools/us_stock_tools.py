"""
US Stock Tools - LangChain Tools for US Stock Analysis

Provides LangChain @tool decorators for US stock data access.
Uses Yahoo Finance as the primary data source.

Available Tools:
- us_stock_price: Real-time price data
- us_technical_analysis: Technical indicators
- us_fundamentals: Fundamental data
- us_earnings: Earnings data and calendar
- us_news: Latest news
- us_institutional_holders: Institutional holdings
- us_insider_transactions: Insider trading data
"""
from langchain.tools import tool
from typing import Optional, List, Dict
import asyncio

from .us_data_provider import get_us_data_provider, USDataProvider


@tool("us_stock_price")
def us_stock_price(symbol: str) -> Dict:
    """
    獲取美股即時價格數據
    
    包含：
    - 當前價格、漲跌、漲跌幅
    - 開盤價、最高價、最低價
    - 成交量、市值
    - 52 週高低點
    
    Args:
        symbol: 美股股票代號（如 AAPL, TSLA, NVDA）
    
    Returns:
        價格數據字典
    """
    try:
        provider = get_us_data_provider()
        # 使用同步方式執行異步函數
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 如果在已有 event loop 的環境中（如 Jupyter）
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass  # 沒有 event loop，正常
        return asyncio.run(provider.get_price(symbol))
    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol,
        }


@tool("us_technical_analysis")
def us_technical_analysis(symbol: str) -> Dict:
    """
    美股技術指標分析
    
    計算指標：
    - RSI (14 日相對強弱指標)
    - MACD (移動平均收斂發散)
    - 移動平均 (20/50/200 日)
    - 布林帶
    - 成交量分析
    
    Args:
        symbol: 美股股票代號
    
    Returns:
        技術指標字典
    """
    try:
        provider = get_us_data_provider()
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass
        return asyncio.run(provider.get_technicals(symbol))
    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol,
        }


@tool("us_fundamentals")
def us_fundamentals(symbol: str) -> Dict:
    """
    美股基本面數據
    
    Args:
        symbol: 美股股票代號
    
    Returns:
        基本面數據字典
    """
    try:
        provider = get_us_data_provider()
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass
        return asyncio.run(provider.get_fundamentals(symbol))
    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol,
        }


@tool("us_earnings")
def us_earnings(symbol: str) -> Dict:
    """
    美股財報數據
    
    Args:
        symbol: 美股股票代號
    
    Returns:
        財報數據字典
    """
    try:
        provider = get_us_data_provider()
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass
        return asyncio.run(provider.get_earnings(symbol))
    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol,
        }


@tool("us_news")
def us_news(symbol: str, limit: int = 5) -> List[Dict]:
    """
    美股相關新聞
    
    Args:
        symbol: 美股股票代號
        limit: 新聞數量上限（預設 5，最多 20）
    
    Returns:
        新聞列表
    """
    try:
        provider = get_us_data_provider()
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass
        return asyncio.run(provider.get_news(symbol, min(limit, 20)))
    except Exception as e:
        return []


@tool("us_institutional_holders")
def us_institutional_holders(symbol: str) -> Dict:
    """
    美股機構持倉數據
    
    Args:
        symbol: 美股股票代號
    
    Returns:
        機構持倉字典
    """
    try:
        provider = get_us_data_provider()
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass
        return asyncio.run(provider.get_institutional_holders(symbol))
    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol,
        }


@tool("us_insider_transactions")
def us_insider_transactions(symbol: str) -> Dict:
    """
    美股內部人交易數據
    
    Args:
        symbol: 美股股票代號
    
    Returns:
        內部人交易字典
    """
    try:
        provider = get_us_data_provider()
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass
        return asyncio.run(provider.get_insider_transactions(symbol))
    except Exception as e:
        return {
            "error": str(e),
            "symbol": symbol,
        }


# ============ 工具註冊函數 ============

def register_us_stock_tools(tool_registry):
    """
    註冊所有美股工具到工具註冊表
    
    Args:
        tool_registry: ToolRegistry 實例
    """
    from core.agents.tool_registry import ToolMetadata
    
    tools = [
        ("us_stock_price", us_stock_price, "獲取美股即時價格數據"),
        ("us_technical_analysis", us_technical_analysis, "美股技術指標分析"),
        ("us_fundamentals", us_fundamentals, "美股基本面數據"),
        ("us_earnings", us_earnings, "美股財報數據"),
        ("us_news", us_news, "美股相關新聞"),
        ("us_institutional_holders", us_institutional_holders, "美股機構持倉數據"),
        ("us_insider_transactions", us_insider_transactions, "美股內部人交易數據"),
    ]
    
    for name, tool_func, desc in tools:
        # 創建 ToolMetadata
        metadata = ToolMetadata(
            name=name,
            description=desc,
            input_schema={"symbol": "str", "limit": "int (optional)"},
            handler=tool_func,
            allowed_agents=["us_stock", "crypto", "full_analysis", "manager"],
        )
        tool_registry.register(metadata)


# ============ 快速測試 ============

if __name__ == "__main__":
    import json
    
    print("測試美股工具...")
    print("=" * 70)
    
    # 測試價格
    print("\n[1] 測試 us_stock_price (AAPL)")
    result = us_stock_price.invoke({"symbol": "AAPL"})
    print(f"價格：${result.get('price', 'N/A')}")
    print(f"漲跌：{result.get('change', 0):+.2f} ({result.get('change_percent', 0):+.2f}%)")
    
    # 測試技術指標
    print("\n[2] 測試 us_technical_analysis (AAPL)")
    result = us_technical_analysis.invoke({"symbol": "AAPL"})
    print(f"RSI: {result.get('rsi', 'N/A')}")
    print(f"綜合訊號：{result.get('summary', 'N/A')}")
    
    # 測試基本面
    print("\n[3] 測試 us_fundamentals (AAPL)")
    result = us_fundamentals.invoke({"symbol": "AAPL"})
    print(f"P/E: {result.get('pe_ratio', 'N/A')}")
    print(f"ROE: {result.get('roe', 'N/A')}")
    
    # 測試新聞
    print("\n[4] 測試 us_news (AAPL)")
    result = us_news.invoke({"symbol": "AAPL", "limit": 3})
    print(f"獲取 {len(result)} 則新聞")
    if result:
        print(f"最新：{result[0].get('title', 'N/A')}")
    
    print("\n" + "=" * 70)
    print("測試完成！")
