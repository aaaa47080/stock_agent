"""
價格與分析工具
Technical Analysis, News Analysis, Price Data, Market Movement, Backtest
"""
from typing import Optional
from langchain_core.tools import tool

from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
from data.data_processor import (
    fetch_and_process_klines,
    extract_technical_indicators,
    calculate_key_levels,
    analyze_market_structure
)
from utils.utils import safe_float, get_crypto_news

from ..schemas import (
    TechnicalAnalysisInput,
    NewsAnalysisInput,
    PriceInput,
    MarketPulseInput,
)
from ..helpers import normalize_symbol, find_available_exchange, format_price


@tool(args_schema=TechnicalAnalysisInput)
def technical_analysis_tool(
    symbol: str,
    interval: str = "1d",
    exchange: Optional[str] = None
) -> str:
    """執行加密貨幣的純技術分析"""
    try:
        if exchange is None:
            exchange, normalized_symbol = find_available_exchange(symbol)
            if exchange is None:
                return f"錯誤：無法在支持的交易所中找到 {symbol} 交易對。"
        else:
            normalized_symbol = normalize_symbol(symbol, exchange)

        df_with_indicators, _ = fetch_and_process_klines(
            symbol=normalized_symbol, interval=interval, limit=200,
            market_type="spot", exchange=exchange
        )

        latest = df_with_indicators.iloc[-1]
        current_price = safe_float(latest['Close'])
        indicators = extract_technical_indicators(latest)
        market_structure = analyze_market_structure(df_with_indicators)
        trend = market_structure.get("趨勢", "不明")
        key_levels = calculate_key_levels(df_with_indicators, period=30)
        support = key_levels.get("支撐位", 0)
        resistance = key_levels.get("壓力位", 0)

        rsi = indicators.get('RSI_14', 50)
        rsi_status = "超買區域" if rsi > 70 else "超賣區域" if rsi < 30 else "偏強勢" if rsi > 60 else "偏弱勢" if rsi < 40 else "中性區域"

        macd = indicators.get('MACD_線', 0)
        macd_status = "多頭動能" if macd > 0 else "空頭動能" if macd < 0 else "動能中性"

        return f"""## {symbol} 技術分析報告 ({interval} 週期)

### 價格資訊
- **當前價格**: {format_price(current_price)}
- **7日趨勢**: {trend}
- **波動率**: {market_structure.get('波動率', 0):.2f}%

### 技術指標
| 指標 | 數值 | 解讀 |
| RSI (14) | {rsi:.2f} | {rsi_status} |
| MACD | {macd:.6f} | {macd_status} |
| MA7 | {format_price(indicators.get('MA_7', 0))} | - |
| MA25 | {format_price(indicators.get('MA_25', 0))} | - |

### 關鍵價位
- **支撐位**: {format_price(support)}
- **壓力位**: {format_price(resistance)}

交易所: {exchange.upper()} | 交易對: {normalized_symbol}
"""
    except SymbolNotFoundError:
        return f"錯誤：找不到交易對 {symbol}。"
    except Exception as e:
        return f"技術分析時發生錯誤: {str(e)}"


@tool(args_schema=NewsAnalysisInput)
def news_analysis_tool(symbol: str, include_sentiment: bool = True) -> str:
    """執行加密貨幣的新聞面分析"""
    try:
        base_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")
        news_data = get_crypto_news(symbol=base_symbol, limit=10)

        if not news_data:
            return f"目前沒有找到 {symbol} 的最新新聞。"

        positive_keywords = ['surge', 'rally', 'bullish', 'gain', 'rise', 'up', 'high', 'buy', 'launch', '上漲', '利好', '突破', 'approval', 'partnership', 'adoption', 'upgrade', 'halving', 'ETF', 'institutional']
        negative_keywords = ['crash', 'bearish', 'drop', 'fall', 'down', 'low', 'sell', 'hack', 'scam', '下跌', '利空', '暴跌', 'ban', 'regulation', 'crackdown', 'dump', 'lawsuit', 'delisting']

        positive_news, negative_news, neutral_news = [], [], []
        for news in news_data[:8]:
            title = news.get('title', '').lower()
            has_positive = any(kw in title for kw in positive_keywords)
            has_negative = any(kw in title for kw in negative_keywords)
            if has_positive and not has_negative:
                positive_news.append(news)
            elif has_negative and not has_positive:
                negative_news.append(news)
            else:
                neutral_news.append(news)

        result = f"## {symbol} 最新新聞動態 📰\n\n📊 共 {len(news_data)} 條 | 🟢 {len(positive_news)} 利多 | 🔴 {len(negative_news)} 利空\n\n"

        if positive_news:
            result += "### 🟢 利多消息\n" + "\n".join([f"- {n.get('title', 'N/A')}" for n in positive_news[:3]]) + "\n\n"
        if negative_news:
            result += "### 🔴 利空消息\n" + "\n".join([f"- {n.get('title', 'N/A')}" for n in negative_news[:3]]) + "\n"

        return result
    except Exception as e:
        return f"新聞分析時發生錯誤: {str(e)}"


@tool(args_schema=PriceInput)
def get_crypto_price_tool(symbol: str, exchange: Optional[str] = None) -> str:
    """
    查詢在主流交易所上市的加密貨幣即時價格（支持 BTC、ETH、SOL 等）。

    ⚠️ 此工具不支持 PI (Pi Network)，查詢 PI 價格請使用 get_pi_price 工具。

    適用於 Binance、OKX 等主流交易所的代幣。
    """
    try:
        if exchange is None:
            exchange, normalized_symbol = find_available_exchange(symbol)
            if exchange is None:
                return f"錯誤：無法找到 {symbol} 交易對。"
        else:
            normalized_symbol = normalize_symbol(symbol, exchange)

        fetcher = get_data_fetcher(exchange)
        klines = fetcher.get_historical_klines(normalized_symbol, "1m", limit=1)

        if klines is None or klines.empty:
            return f"錯誤：無法獲取 {symbol} 的價格數據。"

        current_price = safe_float(klines.iloc[-1]['Close'])

        change_text = "N/A"
        try:
            klines_24h = fetcher.get_historical_klines(normalized_symbol, "1h", limit=24)
            if klines_24h is not None and len(klines_24h) >= 24:
                price_24h_ago = safe_float(klines_24h.iloc[0]['Close'])
                if price_24h_ago > 0:
                    change_24h = ((current_price / price_24h_ago) - 1) * 100
                    change_text = f"+{change_24h:.2f}%" if change_24h >= 0 else f"{change_24h:.2f}%"
        except Exception:
            pass

        return f"## {symbol} 即時價格\n\n- **價格**: {format_price(current_price)}\n- **24h變化**: {change_text}\n- **交易所**: {exchange.upper()}"
    except SymbolNotFoundError:
        return f"錯誤：找不到交易對 {symbol}。"
    except Exception as e:
        return f"價格查詢時發生錯誤: {str(e)}"


@tool(args_schema=MarketPulseInput)
def explain_market_movement_tool(symbol: str) -> str:
    """解釋加密貨幣的價格波動原因"""
    try:
        from analysis.market_pulse import get_market_pulse
        base_symbol = symbol.upper().replace("USDT", "").replace("-", "")
        result = get_market_pulse(base_symbol)
        if "error" in result:
            return result["error"]
        return f"### 💡 {base_symbol} 市場脈動\n\n{result.get('explanation', '暫無解釋')}"
    except Exception as e:
        return f"分析市場波動時發生錯誤: {str(e)}"

