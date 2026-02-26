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
    PriceInput,
    MarketPulseInput,
    BacktestStrategyInput,
    ExtractCryptoSymbolsInput
)
from .helpers import normalize_symbol, find_available_exchange, extract_crypto_symbols


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


# ============================================
# 專業級市場與衍生品數據工具
# ============================================

@tool
def get_fear_and_greed_index() -> str:
    """
    獲取加密貨幣市場全域的恐慌與貪婪指數 (Fear and Greed Index)。
    數值從 0 (極度恐慌) 到 100 (極度貪婪)。非常適合用來判斷市場整體情緒是否過熱或過度悲觀。
    """
    import httpx
    try:
        resp = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and "data" in data and len(data["data"]) > 0:
                current = data["data"][0]
                val = str(current.get("value")).strip()
                classification = str(current.get("value_classification")).strip()
                return f"## 🌡️ 全球加密貨幣市場恐慌與貪婪指數\n\n- **當前指數**: {val} / 100\n- **市場情緒**: {classification}"
        return "目前無法取得恐慌與貪婪指數 API。"
    except Exception as e:
        return f"取得恐慌與貪婪指數時發生網路錯誤: {str(e)}"


# ============================================
# 簡單的 In-Memory TTL Cache (防禦 CoinGecko API Rate Limit)
# ============================================
import time

_COINGECKO_CACHE = {}

def _get_cached_coingecko_data(key: str, ttl_seconds: int = 300):
    if key in _COINGECKO_CACHE:
        timestamp, data = _COINGECKO_CACHE[key]
        if time.time() - timestamp < ttl_seconds:
            return data
    return None

def _set_cached_coingecko_data(key: str, data):
    _COINGECKO_CACHE[key] = (time.time(), data)


@tool
def get_trending_tokens() -> str:
    """
    獲取目前全網最熱門搜尋的加密貨幣 (Trending Tokens)。
    當使用者詢問「現在流行什麼幣」、「市場熱點在哪」時非常有用。
    """
    cache_key = "trending_tokens"
    cached_data = _get_cached_coingecko_data(cache_key, 300)
    if cached_data:
        return cached_data

    import httpx
    try:
        resp = httpx.get("https://api.coingecko.com/api/v3/search/trending", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            coins = data.get("coins", [])
            if not coins:
                return "目前 CoinGecko 無熱門搜尋數據。"
            
            result = "## 🔥 全網熱門搜尋幣種 (Top Trending)\n\n"
            for i, item in enumerate(coins[:7], 1):
                coin = item.get("item", {})
                symbol = coin.get("symbol", "").upper()
                name = coin.get("name", "")
                market_cap_rank = coin.get("market_cap_rank", "N/A")
                result += f"{i}. **{symbol}** ({name}) - 市值排名: {market_cap_rank}\n"
            
            final_output = result + "\n*(資料來源: CoinGecko)*"
            _set_cached_coingecko_data(cache_key, final_output)
            return final_output
        return "目前無法連線到 CoinGecko API 取得熱門搜尋幣種。"
    except Exception as e:
        return f"取得熱門搜尋幣種時發生網路錯誤: {str(e)}"


@tool
def get_futures_data(symbol: str) -> str:
    """
    獲取加密貨幣永續合約的資金費率 (Funding Rate)。
    資金費率正值代表多頭支付空頭 (看多情緒強烈)，負值代表空頭支付多頭 (看空情緒強烈)。
    """
    import httpx
    try:
        base_symbol = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("-", "")
        binance_symbol = f"{base_symbol}USDT"
        
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        resp = httpx.get(url, params={"symbol": binance_symbol}, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            funding_rate = float(data.get("lastFundingRate", 0))
            funding_rate_pct = funding_rate * 100
            
            status = "中立"
            if funding_rate_pct > 0.01:
                status = "🌟 極度熱觀 (多頭擁擠，須注意回調風險)"
            elif funding_rate_pct > 0.005:
                status = "📈 偏多 (多頭支付資金費給空頭)"
            elif funding_rate_pct < -0.01:
                status = "🩸 極度悲觀 (空頭擁擠，須注意軋空風險)"
            elif funding_rate_pct < 0:
                status = "📉 偏空 (空頭支付資金費給多頭)"
            
            return f"## ⚖️ {base_symbol} 合約市場資金費率\n\n- **當前資金費率**: {funding_rate_pct:.4f}%\n- **市場多空情緒**: {status}\n\n*(資料來源: Binance U本位合約)*"
        else:
            return f"找不到 {symbol} 的合約數據，可能在幣安沒有合約對。"
    except Exception as e:
        return f"取得資金費率時發生網路錯誤: {str(e)}"


@tool
def get_current_time_taipei() -> str:
    """
    獲取目前台灣/UTC+8的精準時間與日期。
    當需要分析最新新聞、比對K線時間，或是回答「現在什麼時候」時必備。
    """
    from datetime import datetime
    import pytz
    
    tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(tz)
    
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M:%S")
    weekday_str = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    
    return f"🕰️ 【當前系統時間 (UTC+8)】\n日期：{date_str} ({weekday_str})\n時間：{time_str}"


@tool
def get_defillama_tvl(protocol_name: str) -> str:
    """
    從 DefiLlama 獲取特定協議或公鏈的 TVL (總鎖倉價值)。
    TVL 是衡量 DeFi 專案或公鏈生態健康度與資金流入的最重要基本面指標。
    輸入參數請使用英文名稱，例如 'solana', 'ethereum', 'lido', 'aave'。
    """
    import httpx
    try:
        # 轉換為標準小寫 slug
        slug = protocol_name.strip().lower().replace(" ", "-")
        
        # 先嘗試作為 protocol 查詢
        resp = httpx.get(f"https://api.llama.fi/protocol/{slug}", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("name", protocol_name)
            
            # 取得目前的 TVL 總和
            current_chain_tvls = data.get("currentChainTvls", {})
            if current_chain_tvls:
                tvl = sum(current_chain_tvls.values())
            else:
                tvl_data = data.get("tvl", [])
                tvl = tvl_data[-1].get("totalLiquidityUSD", 0) if isinstance(tvl_data, list) and tvl_data else 0
            
            # 格式化 TVL 為億或百萬美元
            if tvl > 0:
                if tvl > 1_000_000_000:
                    tvl_str = f"${tvl / 1_000_000_000:.2f} 十億 (Billion)"
                else:
                    tvl_str = f"${tvl / 1_000_000:.2f} 百萬 (Million)"
                    
                return f"## 🏦 DefiLlama 鎖倉量 (TVL) 報告\n\n- **協議/公鏈**: {name}\n- **當前總鎖倉價值**: {tvl_str}\n\n*(資料來源: DefiLlama API)*"
        
        # 如果 protocol 查不到，或 TVL 為 0 (可能是純公鏈)，嘗試查 chain
        chains_resp = httpx.get("https://api.llama.fi/v2/chains", timeout=10)
        if chains_resp.status_code == 200:
            chains = chains_resp.json()
            for chain in chains:
                c_name = (chain.get("name") or "").lower()
                c_symbol = (chain.get("tokenSymbol") or "").lower()
                if c_name == slug or c_symbol == slug:
                    tvl = chain.get("tvl", 0)
                    if tvl > 1_000_000_000:
                        tvl_str = f"${tvl / 1_000_000_000:.2f} 十億 (Billion)"
                    else:
                        tvl_str = f"${tvl / 1_000_000:.2f} 百萬 (Million)"
                    return f"## 🏦 DefiLlama 公鏈鎖倉量 (TVL)\n\n- **公鏈名稱**: {chain.get('name')}\n- **當前總鎖倉價值**: {tvl_str}\n\n*(資料來源: DefiLlama API)*"
        
        return f"在 DefiLlama 查不到 '{protocol_name}' 的資料，請確認拼字是否正確 (如: solana, aave)。"
    except Exception as e:
        return f"取得 TVL 數據時發生網路錯誤: {str(e)}"


@tool
def get_crypto_categories_and_gainers() -> str:
    """
    獲取 CoinGecko 上表現最佳的加密貨幣板塊 (Sectors/Categories) 與全網領漲幣種。
    當需要分析「今日市場資金流向何處」、「目前在炒作什麼概念」時必備。
    """
    cache_key = "categories_and_gainers"
    cached_data = _get_cached_coingecko_data(cache_key, 300)
    if cached_data:
        return cached_data

    import httpx
    try:
        # 1. 獲取熱門 categories
        cat_resp = httpx.get("https://api.coingecko.com/api/v3/coins/categories", timeout=10)
        
        output = "## 🚀 加密貨幣市場動能與資金流向分析\n\n"
        
        if cat_resp.status_code == 200:
            categories = cat_resp.json()
            # 根據 24h 漲跌幅排序
            sorted_cats = sorted(
                [c for c in categories if c.get('market_cap_change_24h') is not None],
                key=lambda x: x['market_cap_change_24h'], 
                reverse=True
            )
            
            output += "### 🌟 今日最強勢板塊 (Top Sectors)\n"
            for i, cat in enumerate(sorted_cats[:5], 1):
                name = cat.get("name", "Unknown")
                change = cat.get("market_cap_change_24h", 0)
                output += f"{i}. **{name}**: {change:+.2f}%\n"
        else:
            output += "*(暫時無法獲取板塊數據)*\n"
            
        final_output = output + "\n*(資料來源: CoinGecko)*"
        _set_cached_coingecko_data(cache_key, final_output)
        return final_output
    except Exception as e:
        return f"取得板塊數據時發生網路錯誤: {str(e)}"


@tool
def get_token_unlocks(symbol: str) -> str:
    """
    獲取代幣未來的解鎖日程與數量 (Token Unlocks)。
    代幣解鎖通常會增加市場流通量，對價格產生拋售壓力。
    當使用者詢問「有沒有解鎖」、「會不會砸盤」或進行基本面籌碼面分析時必備。
    注意：此為展示用數據模組 (Mock API)，僅提供重點公鏈的模擬示範。
    """
    symbol = symbol.upper()
    
    # 這裡實作一個精美的 Mock Data 來展示 Agent 處理籌碼面壓力的能力
    mock_data = {
        "SUI": {"date": "本月 15 日", "amount": "64.19M SUI", "usd": "$105M", "percent": "2.26%"},
        "APT": {"date": "下週三", "amount": "11.31M APT", "usd": "$98M", "percent": "2.48%"},
        "ARB": {"date": "下個月 16 日", "amount": "92.65M ARB", "usd": "$53M", "percent": "2.87%"},
        "OP": {"date": "本週五", "amount": "31.34M OP", "usd": "$43M", "percent": "2.5%"}
    }
    
    if symbol in ['BTC', 'ETH']:
        return f"✅ **{symbol} 代幣解鎖報告**\n\n{symbol} 為 PoW 或無定期大量解鎖機制的代幣，目前沒有任何即將到來的大額懸崖解鎖 (Cliff Unlocks) 拋壓。"
    
    if symbol in mock_data:
        unlock = mock_data[symbol]
        return f"⚠️ **{symbol} 即將迎來大額代幣解鎖！**\n\n- **解鎖時間**: {unlock['date']}\n- **解鎖數量**: {unlock['amount']} (約價值 {unlock['usd']})\n- **佔流通量比例**: 增加 {unlock['percent']}\n\n*警告: 高比例的解鎖可能會為現貨市場帶來短期的拋售壓力，請注意風險。*\n*(資料來源: TokenUnlocks 模擬數據)*"
    
    return f"ℹ️ **{symbol} 代幣解鎖報告**\n\n目前沒有監測到 {symbol} 在未來兩週內有超過流通量 1% 的大額懸崖解鎖。拋售壓力相對安全。\n*(資料來源: TokenUnlocks 模擬數據)*"

@tool
def get_token_supply(symbol: str) -> str:
    """
    獲取指定加密貨幣的代幣經濟學數據 (Tokenomics)，包含：
    - Circulating Supply (目前市場流通量)
    - Total Supply (總發行量)
    - Max Supply (最大供應量上限，若有)
    
    使用情境：用戶詢問代幣發行量、目前有多少顆在流通、或是總量上限時使用。
    """
    symbol = symbol.upper()
    cache_key = f"token_supply_{symbol}"
    cached_data = _get_cached_coingecko_data(cache_key, 600)  # 供應量變動不頻繁，快取 10 分鐘
    if cached_data:
        return cached_data

    import httpx
    try:
        # 1. First, search CoinGecko for the internal coin id using the symbol
        search_resp = httpx.get(f"https://api.coingecko.com/api/v3/search?query={symbol}", timeout=10)
        search_resp.raise_for_status()
        search_data = search_resp.json()
        
        coins = search_data.get("coins", [])
        if not coins:
            return f"找不到 {symbol} 的代幣資訊，請確認代幣代號是否正確。"
            
        # Try to find an exact symbol match (case-insensitive) as the first choice, otherwise take the first result
        coin_id = coins[0]["id"]
        coin_name = coins[0]["name"]
        for c in coins:
            if c.get("symbol", "").upper() == symbol:
                coin_id = c["id"]
                coin_name = c["name"]
                break
                
        # 2. Query the exact coin details to get supply data
        detail_resp = httpx.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false", timeout=10)
        detail_resp.raise_for_status()
        detail_data = detail_resp.json()
        
        market_data = detail_data.get("market_data", {})
        
        circulating = market_data.get("circulating_supply")
        total = market_data.get("total_supply")
        max_supply = market_data.get("max_supply")
        
        def format_supply(value):
            if value is None:
                return "未知/無上限"
            if value > 1_000_000_000:
                return f"{value / 1_000_000_000:.2f} 十億 (Billion) 顆"
            elif value > 1_000_000:
                return f"{value / 1_000_000:.2f} 百萬 (Million) 顆"
            else:
                return f"{value:,.0f} 顆"
                
        circulating_str = format_supply(circulating)
        total_str = format_supply(total)
        max_str = format_supply(max_supply)
        
        final_output = (
            f"## 🪙 {coin_name} ({symbol}) 代幣供應量報告\n\n"
            f"- **目前流通量 (Circulating Supply)**: {circulating_str}\n"
            f"- **總發行量 (Total Supply)**: {total_str}\n"
            f"- **最大供應量上限 (Max Supply)**: {max_str}\n\n"
            f"*(資料來源: CoinGecko API)*"
        )
        _set_cached_coingecko_data(cache_key, final_output)
        return final_output
        
    except Exception as e:
        return f"獲取 {symbol} 代幣供應量時發生錯誤: {str(e)}，目前無法取得數據。"


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
