"""
加密貨幣分析工具
所有與加密貨幣相關的 LangChain 工具
"""

from typing import Optional, Dict
from langchain_core.tools import tool

from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
from data.data_processor import (
    fetch_and_process_klines,
    extract_technical_indicators,
    calculate_key_levels,
    analyze_market_structure
)
from utils.utils import safe_float, get_crypto_news
from core.config import DEFAULT_KLINES_LIMIT

from .schemas import (
    TechnicalAnalysisInput,
    NewsAnalysisInput,
    FullInvestmentAnalysisInput,
    PriceInput,
    MarketPulseInput,
    BacktestStrategyInput,
    ExtractCryptoSymbolsInput
)
from .helpers import normalize_symbol, find_available_exchange, extract_crypto_symbols
from .formatters import format_full_analysis_result


@tool(args_schema=TechnicalAnalysisInput)
def technical_analysis_tool(
    symbol: str,
    interval: str = "1d",
    exchange: Optional[str] = None
) -> str:
    """
    執行加密貨幣的純技術分析。

    分析內容包括：
    - RSI (相對強弱指標)
    - MACD (移動平均收斂/發散指標)
    - 布林帶 (Bollinger Bands)
    - 移動平均線 (MA7, MA25)
    - 趨勢判斷
    - 支撐位和壓力位

    適用情境：
    - 用戶詢問技術指標數值（如 RSI、MACD）
    - 用戶想知道是否超買/超賣
    - 用戶詢問趨勢方向
    - 用戶詢問支撐壓力位
    """
    try:
        # 自動選擇交易所
        if exchange is None:
            exchange, normalized_symbol = find_available_exchange(symbol)
            if exchange is None:
                return f"錯誤：無法在支持的交易所中找到 {symbol} 交易對。請確認幣種名稱是否正確。"
        else:
            normalized_symbol = normalize_symbol(symbol, exchange)

        # 獲取 K線數據並計算技術指標
        df_with_indicators, _ = fetch_and_process_klines(
            symbol=normalized_symbol,
            interval=interval,
            limit=200,
            market_type="spot",
            exchange=exchange
        )

        latest = df_with_indicators.iloc[-1]
        current_price = safe_float(latest['Close'])

        # 提取技術指標
        indicators = extract_technical_indicators(latest)

        # 計算趨勢和市場結構
        market_structure = analyze_market_structure(df_with_indicators)
        trend = market_structure.get("趨勢", "不明")

        # 計算關鍵價位
        key_levels = calculate_key_levels(df_with_indicators, period=30)
        support = key_levels.get("支撐位", 0)
        resistance = key_levels.get("壓力位", 0)

        # RSI 解讀
        rsi = indicators.get('RSI_14', 50)
        if rsi > 70:
            rsi_status = "超買區域 (建議謹慎追高)"
        elif rsi < 30:
            rsi_status = "超賣區域 (可能有反彈機會)"
        elif rsi > 60:
            rsi_status = "偏強勢"
        elif rsi < 40:
            rsi_status = "偏弱勢"
        else:
            rsi_status = "中性區域"

        # MACD 解讀
        macd = indicators.get('MACD_線', 0)
        if macd > 0:
            macd_status = "多頭動能"
        elif macd < 0:
            macd_status = "空頭動能"
        else:
            macd_status = "動能中性"

        # 格式化輸出
        result = f"""## {symbol} 技術分析報告 ({interval} 週期)

### 價格資訊
- **當前價格**: ${current_price:.4f}
- **7日趨勢**: {trend}
- **波動率**: {market_structure.get('波動率', 0):.2f}%

### 技術指標
| 指標 | 數值 | 解讀 |
|------|------|------|
| RSI (14) | {rsi:.2f} | {rsi_status} |
| MACD | {macd:.6f} | {macd_status} |
| MA7 | ${indicators.get('MA_7', 0):.4f} | - |
| MA25 | ${indicators.get('MA_25', 0):.4f} | - |
| 布林帶上軌 | ${indicators.get('布林帶上軌', 0):.4f} | - |
| 布林帶下軌 | ${indicators.get('布林帶下軌', 0):.4f} | - |

### 關鍵價位
- **支撐位**: ${support:.4f}
- **壓力位**: ${resistance:.4f}
- **30日最高**: ${key_levels.get('30天最高價', 0):.4f}
- **30日最低**: ${key_levels.get('30天最低價', 0):.4f}

### 數據來源
交易所: {exchange.upper()} | 交易對: {normalized_symbol}
"""
        return result

    except SymbolNotFoundError:
        return f"錯誤：找不到交易對 {symbol}。請確認幣種名稱是否正確。"
    except Exception as e:
        return f"技術分析時發生錯誤: {str(e)}"
    

@tool(args_schema=NewsAnalysisInput)
def news_analysis_tool(
    symbol: str,
    include_sentiment: bool = True
) -> str:
    """
    執行加密貨幣的新聞面分析。

    分析內容包括：
    - 最新市場新聞
    - 新聞情緒判斷 (利多/利空/中性)
    - 重要事件識別

    適用情境：
    - 用戶詢問某幣種的最新新聞
    - 用戶想了解市場情緒
    - 用戶詢問近期有什麼重大消息
    """
    try:
        # 清理 symbol
        base_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")

        # 獲取新聞
        news_data = get_crypto_news(symbol=base_symbol, limit=10)

        if not news_data:
            return f"目前沒有找到 {symbol} 的最新新聞。這可能是因為該幣種較新或新聞來源暫時無法連接。"

        # 分類新聞
        positive_keywords = ['surge', 'rally', 'bullish', 'gain', 'rise', 'up', 'high', 'buy', 'launch', '上漲', '利好', '突破', 'approval', 'partnership', 'adoption', 'upgrade', 'halving', 'ETF', 'institutional']
        negative_keywords = ['crash', 'bearish', 'drop', 'fall', 'down', 'low', 'sell', 'hack', 'scam', '下跌', '利空', '暴跌', 'ban', 'regulation', 'crackdown', 'dump', 'lawsuit', 'delisting']

        positive_news = []
        negative_news = []
        neutral_news = []

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

        # 格式化新聞列表
        news_sections = []

        if positive_news:
            positive_list = []
            for i, news in enumerate(positive_news, 1):
                title = news.get('title', 'N/A')
                source = news.get('source', 'Unknown')
                url = news.get('url', '')
                news_item = f"{i}. **{title}**\n   來源: {source}"
                if url:
                    news_item += f" | [閱讀更多]({url})"
                positive_list.append(news_item)
            news_sections.append(f"### 🟢 正面新聞 ({len(positive_news)} 條)\n" + "\n\n".join(positive_list))

        if negative_news:
            negative_list = []
            for i, news in enumerate(negative_news, 1):
                title = news.get('title', 'N/A')
                source = news.get('source', 'Unknown')
                url = news.get('url', '')
                news_item = f"{i}. **{title}**\n   來源: {source}"
                if url:
                    news_item += f" | [閱讀更多]({url})"
                negative_list.append(news_item)
            news_sections.append(f"\n### 🔴 負面新聞 ({len(negative_news)} 條)\n" + "\n\n".join(negative_list))

        if neutral_news:
            neutral_list = []
            for i, news in enumerate(neutral_news, 1):
                title = news.get('title', 'N/A')
                source = news.get('source', 'Unknown')
                url = news.get('url', '')
                news_item = f"{i}. **{title}**\n   來源: {source}"
                if url:
                    news_item += f" | [閱讀更多]({url})"
                neutral_list.append(news_item)
            news_sections.append(f"\n### 🔵 中性新聞 ({len(neutral_news)} 條)\n" + "\n\n".join(neutral_list))

        result = f"""## {symbol} 最新新聞動態 📰

📊 **總覽**: 共 {len(news_data)} 條新聞 | 🟢 {len(positive_news)} 利多 | 🔴 {len(negative_news)} 利空 | 🔵 {len(neutral_news)} 中性

{chr(10).join(news_sections) if news_sections else ""}

"""

        if include_sentiment:
            if len(positive_news) > len(negative_news):
                sentiment = "偏正面 (利多消息較多)"
            elif len(negative_news) > len(positive_news):
                sentiment = "偏負面 (利空消息較多)"
            else:
                sentiment = "中性 (無明顯傾向)"

            result += f"""### 簡易情緒分析
- **整體情緒**: {sentiment}
- **正面新聞**: {len(positive_news)} 條
- **負面新聞**: {len(negative_news)} 條

> 注意：此為基於關鍵詞的簡易分析。如需更深入的投資建議，請使用完整投資分析功能。
"""

        return result

    except Exception as e:
        return f"新聞分析時發生錯誤: {str(e)}"


@tool(args_schema=FullInvestmentAnalysisInput)
def full_investment_analysis_tool(
    symbol: str,
    interval: str = "1d",
    include_futures: bool = True,
    leverage: int = 5
) -> str:
    """
    執行完整的加密貨幣投資分析。

    這是最全面的分析工具，包括：
    - 4 位 AI 分析師並行分析 (技術、情緒、基本面、新聞)
    - 多空研究員辯論 (三方辯論模式)
    - 交易決策生成 (具體買賣建議)
    - 風險評估
    - 基金經理最終審批

    適用情境：
    - 用戶詢問「XXX 可以投資嗎？」
    - 用戶詢問「應該買入還是賣出？」
    - 用戶需要完整的投資建議和交易計劃
    - 用戶想要多空辯論結果

    **注意**：此工具執行時間較長 (30秒-2分鐘)，因為需要完整分析流程。
    """
    try:
        # 延遲導入以避免循環依賴
        from core.graph import app as langgraph_app

        # 自動選擇交易所
        exchange, normalized_symbol = find_available_exchange(symbol)
        if exchange is None:
            return f"錯誤：無法在支持的交易所中找到 {symbol} 交易對。請確認幣種名稱是否正確。"

        # 準備現貨分析狀態
        spot_state = {
            "symbol": normalized_symbol,
            "exchange": exchange,
            "interval": interval,
            "limit": DEFAULT_KLINES_LIMIT,
            "market_type": "spot",
            "leverage": 1,
            "include_multi_timeframe": interval == "1d",
            "short_term_interval": "1h",
            "medium_term_interval": "4h",
            "long_term_interval": "1d",
            "preloaded_data": None,
            "account_balance": None,
            "selected_analysts": ["technical", "sentiment", "fundamental", "news"],
            "perform_trading_decision": True
        }

        # 執行分析
        result = langgraph_app.invoke(spot_state)

        # 格式化結果
        output = format_full_analysis_result(result, "現貨", symbol, interval)

        # 如果需要合約分析
        if include_futures:
            futures_state = spot_state.copy()
            futures_state.update({
                "market_type": "futures",
                "leverage": leverage
            })

            try:
                futures_result = langgraph_app.invoke(futures_state)
                output += "\n\n---\n\n"
                output += format_full_analysis_result(futures_result, f"合約 ({leverage}x槓桿)", symbol, interval)
            except Exception as e:
                output += f"\n\n(合約分析暫時無法完成: {str(e)})"

        return output

    except SymbolNotFoundError:
        return f"錯誤：找不到交易對 {symbol}。請確認幣種名稱是否正確。"
    except Exception as e:
        return f"完整投資分析時發生錯誤: {str(e)}"


@tool(args_schema=PriceInput)
def get_crypto_price_tool(
    symbol: str,
    exchange: Optional[str] = None
) -> str:
    """
    查詢加密貨幣的即時價格。

    這是一個輕量級的價格查詢工具，執行速度最快。

    適用情境：
    - 用戶詢問「XXX 現在多少錢？」
    - 用戶詢問「XXX 的價格是多少？」
    - 快速查看價格，不需要完整分析
    """
    try:
        # 自動選擇交易所
        if exchange is None:
            exchange, normalized_symbol = find_available_exchange(symbol)
            if exchange is None:
                return f"錯誤：無法在支持的交易所中找到 {symbol} 交易對。請確認幣種名稱是否正確。"
        else:
            normalized_symbol = normalize_symbol(symbol, exchange)

        # 獲取最新價格
        fetcher = get_data_fetcher(exchange)
        klines = fetcher.get_historical_klines(normalized_symbol, "1m", limit=1)

        if klines is None or klines.empty:
            return f"錯誤：無法獲取 {symbol} 的價格數據。"

        current_price = safe_float(klines.iloc[-1]['Close'])

        # 獲取 24 小時變化
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

        return f"""## {symbol} 即時價格

| 項目 | 數值 |
|------|------|
| **當前價格** | **${current_price:.4f}** |
| 24小時變化 | {change_text} |
| 交易所 | {exchange.upper()} |
| 交易對 | {normalized_symbol} |
"""

    except SymbolNotFoundError:
        return f"錯誤：找不到交易對 {symbol}。請確認幣種名稱是否正確。"
    except Exception as e:
        return f"價格查詢時發生錯誤: {str(e)}"


@tool(args_schema=MarketPulseInput)
def explain_market_movement_tool(symbol: str) -> str:
    """
    解釋加密貨幣的價格波動原因。

    這個工具會結合即時價格變化和最新新聞，生成一句簡短的解釋（敘事歸因）。

    適用情境：
    - 用戶問「為什麼 BTC 跌了？」
    - 用戶問「ETH 為什麼漲這麼多？」
    - 用戶想知道市場波動背後的原因
    """
    try:
        from analysis.market_pulse import get_market_pulse

        # 清理 symbol
        base_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")

        result = get_market_pulse(base_symbol)

        if "error" in result:
            return result["error"]

        explanation = result.get("explanation", "暫無解釋")
        change_1h = result.get("change_1h", 0)
        current_price = result.get("current_price", 0)

        # 構建回應
        output = f"### 💡 市場脈動: {base_symbol}\n\n"
        output += f"**{explanation}**\n\n"
        output += f"- 當前價格: ${current_price:.4f}\n"
        output += f"- 1小時變化: {change_1h:+.2f}%\n"

        # 附上新聞來源
        news = result.get("news_sources", [])
        if news:
            output += "\n**相關新聞**:\n\n"
            for i, n in enumerate(news[:2], 1):
                output += f"{i}. **{n.get('title')}** - {n.get('source')}\n"

        return output

    except Exception as e:
        return f"分析市場波動時發生錯誤: {str(e)}"


@tool(args_schema=BacktestStrategyInput)
def backtest_strategy_tool(
    symbol: str,
    interval: str = "1d",
    period: int = 90
) -> str:
    """
    執行加密貨幣的歷史策略回測。

    此工具會使用過去一段時間的數據，模擬執行常見的技術指標策略（如 RSI逆勢、均線趨勢、布林帶突破），
    並回報其勝率和總回報率。

    適用情境：
    - 用戶問「這個幣最近如果用 RSI 操作會賺錢嗎？」
    - 用戶問「幫我回測一下 BTC」
    - 驗證某個策略在該幣種上的歷史有效性
    """
    try:
        from analysis.backtest_engine import BacktestEngine

        # 自動選擇交易所
        exchange, normalized_symbol = find_available_exchange(symbol)
        if exchange is None:
            return f"錯誤：無法在支持的交易所中找到 {symbol} 交易對。請確認幣種名稱是否正確。"

        # 計算需要的K線數量
        limit = period
        if interval == "1h":
            limit = period * 24
        elif interval == "4h":
            limit = period * 6
        elif interval == "15m":
            limit = period * 96

        # 限制最大 limit
        limit = min(limit, 1000)

        # 獲取數據
        df, _ = fetch_and_process_klines(
            symbol=normalized_symbol,
            interval=interval,
            limit=limit,
            market_type="spot",
            exchange=exchange
        )

        # 執行回測
        engine = BacktestEngine()
        results = engine.run_all_strategies(df)

        if not results or "error" in results[0]:
            return f"回測失敗: {results[0].get('error', '未知錯誤')}"

        # 格式化輸出
        summary = results[0]
        strategies = results[1:]

        output = f"## 📊 {symbol} 歷史策略回測報告\n\n"
        output += f"**回測區間**: 過去 {period} 天 ({len(df)} 根 K 線)\n"
        output += f"**最佳策略**: {summary['best_strategy_name']} (勝率 {summary['best_win_rate']}%)\n\n"
        output += f"> {summary['summary']}\n\n"

        output += "### 詳細表現\n"
        output += "| 策略名稱 | 勝率 | 總回報 | 交易次數 | 評價 |\n"
        output += "|---|---|---|---|---|\n"

        for res in strategies:
            win_rate = f"{res['win_rate']}%"
            ret = f"{res['total_return']:+.2f}%"
            quality = res['signal_quality']

            if res['total_return'] > 0:
                ret = f"🟢 {ret}"
            else:
                ret = f"🔴 {ret}"

            output += f"| {res['strategy']} | {win_rate} | {ret} | {res['total_trades']} | {quality} |\n"

        output += "\n> 注意：過往績效不代表未來表現。此回測僅供參考，未考慮滑點與手續費。\n"

        return output

    except Exception as e:
        return f"執行回測時發生錯誤: {str(e)}"


@tool(args_schema=ExtractCryptoSymbolsInput)
def extract_crypto_symbols_tool(user_query: str) -> Dict:
    """
    從用戶查詢中提取加密貨幣符號。

    這個工具會智能地從用戶的自然語言查詢中識別和提取加密貨幣符號，
    支持中英文混合文本，並返回匹配到的符號列表。

    適用情境：
    - 從混合語言文本中提取加密貨幣符號
    - 當用戶詢問 'BTC現在值得買嗎？' 時提取 'BTC'
    - 當用戶詢問 '比較ETH和SOL' 時提取 ['ETH', 'SOL']
    """
    extracted_symbols = extract_crypto_symbols(user_query)

    return {
        "original_query": user_query,
        "extracted_symbols": extracted_symbols,
        "count": len(extracted_symbols)
    }
