"""
加密貨幣分析 LangChain 工具集
將現有分析功能封裝為 @tool，供 ReAct Agent 調用
"""

import os
import sys
from typing import Optional, Dict, List
from pydantic import BaseModel, Field

# 確保專案根目錄在 Python 路徑中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_core.tools import tool

# 導入現有模組
from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
from data.data_processor import (
    fetch_and_process_klines,
    extract_technical_indicators,
    calculate_key_levels,
    analyze_market_structure,
    calculate_price_info
)
from utils.utils import safe_float, get_crypto_news
from core.config import (
    DEFAULT_INTERVAL,
    DEFAULT_KLINES_LIMIT,
    DEFAULT_FUTURES_LEVERAGE,
    SUPPORTED_EXCHANGES
)


# ============================================================================
# 工具輸入模型定義 (Pydantic Schema)
# ============================================================================

class TechnicalAnalysisInput(BaseModel):
    """技術分析工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣交易對符號，如 'BTC', 'ETH', 'SOL', 'PI'。不需要加 'USDT' 後綴。"
    )
    interval: str = Field(
        default="1d",
        description="K線時間週期。選項: '1m', '5m', '15m', '1h', '4h', '1d', '1w'。預設為日線 '1d'。"
    )
    exchange: Optional[str] = Field(
        default=None,
        description="交易所名稱。選項: 'binance', 'okx'。如不指定，系統會自動選擇。"
    )


class NewsAnalysisInput(BaseModel):
    """新聞分析工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣符號，如 'BTC', 'ETH', 'PI'。"
    )
    include_sentiment: bool = Field(
        default=True,
        description="是否包含情緒分析。預設為 True。"
    )


class FullInvestmentAnalysisInput(BaseModel):
    """完整投資分析工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣交易對符號，如 'BTC', 'ETH', 'PI'。"
    )
    interval: str = Field(
        default="1d",
        description="主要分析的時間週期。預設為日線 '1d'。"
    )
    include_futures: bool = Field(
        default=True,
        description="是否同時分析合約市場。預設為 True。"
    )
    leverage: int = Field(
        default=5,
        ge=1,
        le=125,
        description="合約分析使用的槓桿倍數。預設 5 倍。"
    )


class PriceInput(BaseModel):
    """價格查詢工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣符號，如 'BTC', 'ETH', 'SOL', 'PI'。"
    )
    exchange: Optional[str] = Field(
        default=None,
        description="交易所名稱。選項: 'binance', 'okx'。"
    )


# ============================================================================
# 輔助函數
# ============================================================================

def _normalize_symbol(symbol: str, exchange: str = "binance") -> str:
    """標準化交易對符號"""
    symbol = symbol.upper().strip()
    # 移除可能存在的後綴
    symbol = symbol.replace("USDT", "").replace("BUSD", "").replace("-", "").replace("SWAP", "")

    if exchange.lower() == "okx":
        return f"{symbol}-USDT"
    else:  # binance
        return f"{symbol}USDT"


def _find_available_exchange(symbol: str) -> tuple:
    """查找交易對可用的交易所"""
    for exchange in SUPPORTED_EXCHANGES:
        try:
            normalized = _normalize_symbol(symbol, exchange)
            fetcher = get_data_fetcher(exchange)
            test_data = fetcher.get_historical_klines(normalized, "1d", limit=1)
            if test_data is not None and not test_data.empty:
                return (exchange, normalized)
        except Exception:
            continue
    return (None, None)


# ============================================================================
# 工具實現
# ============================================================================

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
            exchange, normalized_symbol = _find_available_exchange(symbol)
            if exchange is None:
                return f"錯誤：無法在支持的交易所中找到 {symbol} 交易對。請確認幣種名稱是否正確。"
        else:
            normalized_symbol = _normalize_symbol(symbol, exchange)

        # 獲取 K線數據並計算技術指標
        df_with_indicators, _ = fetch_and_process_klines(
            symbol=normalized_symbol,
            interval=interval,
            limit=200,  # 確保有足夠數據計算指標
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

        # 分類新聞為正面、負面、中性
        positive_keywords = ['surge', 'rally', 'bullish', 'gain', 'rise', 'up', 'high', 'buy', 'launch', '上漲', '利好', '突破', 'approval', 'partnership', 'adoption', 'upgrade', 'halving', 'ETF', 'institutional', 'bull', 'moon', 'rocket', 'gain', 'profit', 'success', 'achievement', 'growth', 'expansion', 'investment', 'funding', 'development', 'innovation', 'record', 'high', 'all-time high']
        negative_keywords = ['crash', 'bearish', 'drop', 'fall', 'down', 'low', 'sell', 'hack', 'scam', '下跌', '利空', '暴跌', 'ban', 'regulation', 'crackdown', 'dump', 'fud', 'fear', 'panic', 'lawsuit', 'delisting', 'loss', 'decline', 'decrease', 'bear', 'crash', 'plunge', 'trouble', 'problem', 'failure', 'issue', 'concern', 'worries', 'downside', 'risk', 'volatility', 'crisis', 'shutdown', 'ban', 'prosecution', 'fine', 'penalty']

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

        # 格式化新聞列表按情緒分類
        news_sections = []

        if positive_news:
            positive_list = []
            for i, news in enumerate(positive_news, 1):
                title = news.get('title', 'N/A')
                source = news.get('source', 'Unknown')
                url = news.get('url', '')
                news_item = f"✅ **{title}**\n   來源: {source}"
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
                news_item = f"❌ **{title}**\n   來源: {source}"
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
                news_item = f"⚪ **{title}**\n   來源: {source}"
                if url:
                    news_item += f" | [閱讀更多]({url})"
                neutral_list.append(news_item)
            news_sections.append(f"\n### 🔵 中性新聞 ({len(neutral_news)} 條)\n" + "\n\n".join(neutral_list))

        result = f"""## {symbol} 最新新聞動態 📰

📊 **總覽**: 共 {len(news_data)} 條新聞 | 🟢 {len(positive_news)} 利多 | 🔴 {len(negative_news)} 利空 | 🔵 {len(neutral_news)} 中性

{chr(10).join(news_sections) if news_sections else "📋 無分類新聞 | [閱讀更多]({news_data[0].get('url', '')})" if news_data else ""}


### 📋 新聞摘要
- 共獲取到 **{len(news_data)}** 條相關新聞
- 主要來源包括 CoinGecko、NewsAPI、CryptoPanic 等
- 按情緒分類：正面 {len(positive_news)} 條，負面 {len(negative_news)} 條，中性 {len(neutral_news)} 條

"""

        if include_sentiment:
            # 簡單的情緒分析（基於新聞標題關鍵詞）
            positive_keywords = ['surge', 'rally', 'bullish', 'gain', 'rise', 'up', 'high', 'buy', 'launch', '上漲', '利好', '突破']
            negative_keywords = ['crash', 'bearish', 'drop', 'fall', 'down', 'low', 'sell', 'hack', 'scam', '下跌', '利空', '暴跌']

            positive_count = 0
            negative_count = 0

            for news in news_data:
                title = news.get('title', '').lower()
                if any(kw in title for kw in positive_keywords):
                    positive_count += 1
                if any(kw in title for kw in negative_keywords):
                    negative_count += 1

            if positive_count > negative_count:
                sentiment = "偏正面 (利多消息較多)"
            elif negative_count > positive_count:
                sentiment = "偏負面 (利空消息較多)"
            else:
                sentiment = "中性 (無明顯傾向)"

            result += f"""### 簡易情緒分析
- **整體情緒**: {sentiment}
- **正面新聞**: {positive_count} 條
- **負面新聞**: {negative_count} 條
- **中性新聞**: {len(news_data) - positive_count - negative_count} 條

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
        exchange, normalized_symbol = _find_available_exchange(symbol)
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
        output = _format_full_analysis_result(result, "現貨", symbol, interval)

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
                output += _format_full_analysis_result(futures_result, f"合約 ({leverage}x槓桿)", symbol, interval)
            except Exception as e:
                output += f"\n\n(合約分析暫時無法完成: {str(e)})"

        return output

    except SymbolNotFoundError:
        return f"錯誤：找不到交易對 {symbol}。請確認幣種名稱是否正確。"
    except Exception as e:
        return f"完整投資分析時發生錯誤: {str(e)}"


def _format_full_analysis_result(result: dict, market_type: str, symbol: str, interval: str) -> str:
    """格式化完整分析結果為可讀文本"""

    current_price = result.get('current_price', 0)
    final_approval = result.get('final_approval')
    trader_decision = result.get('trader_decision')
    risk_assessment = result.get('risk_assessment')
    debate_judgment = result.get('debate_judgment')
    analyst_reports = result.get('analyst_reports', [])

    output = f"""## {symbol} {market_type}分析報告 ({interval})

### 當前價格
**${current_price:.4f}**

"""

    # 分析師報告摘要
    if analyst_reports:
        output += "### 分析師觀點摘要\n"
        for report in analyst_reports:
            if report:
                output += f"- **{report.analyst_type}**: 信心度 {report.confidence:.1f}%\n"
        output += "\n"

    # 辯論結果
    if debate_judgment:
        output += f"""### 多空辯論裁決
| 項目 | 結果 |
|------|------|
| 勝出方 | **{debate_judgment.winning_stance}** |
| 多頭得分 | {debate_judgment.bull_score:.1f} |
| 空頭得分 | {debate_judgment.bear_score:.1f} |

**裁判總結**: {debate_judgment.key_takeaway}

"""

    # 交易決策
    if trader_decision:
        entry = f"${trader_decision.entry_price:.4f}" if trader_decision.entry_price else "N/A"
        stop_loss = f"${trader_decision.stop_loss:.4f}" if trader_decision.stop_loss else "N/A"
        take_profit = f"${trader_decision.take_profit:.4f}" if trader_decision.take_profit else "N/A"

        output += f"""### 交易決策
| 項目 | 建議 |
|------|------|
| **決策** | **{trader_decision.decision}** |
| 進場價 | {entry} |
| 止損 | {stop_loss} |
| 止盈 | {take_profit} |
| 建議倉位 | {trader_decision.position_size * 100:.1f}% |
| 信心度 | {trader_decision.confidence:.1f}% |

**決策理由**: {trader_decision.reasoning}

"""

    # 風險評估
    if risk_assessment:
        output += f"""### 風險評估
- **風險等級**: {risk_assessment.risk_level}
- **評估意見**: {risk_assessment.assessment}
- **調整後倉位**: {risk_assessment.adjusted_position_size * 100:.1f}%
"""
        if risk_assessment.warnings:
            output += f"- **警告**: {', '.join(risk_assessment.warnings)}\n"
        output += "\n"

    # 最終審批
    if final_approval:
        output += f"""### 最終審批 (基金經理)
| 項目 | 結果 |
|------|------|
| **最終決定** | **{final_approval.final_decision}** |
| 最終倉位 | {final_approval.final_position_size * 100:.1f}% |

**執行建議**: {final_approval.execution_notes}

**審批理由**: {final_approval.rationale}
"""

    # 附錄：真實新聞列表
    market_data = result.get('market_data', {})
    news_data = market_data.get('新聞資訊', [])
    if news_data:
        output += "\n### 📰 相關新聞快訊\n"
        for i, news in enumerate(news_data[:5], 1):
            title = news.get('title', 'N/A')
            url = news.get('url', '')
            source = news.get('source', 'Unknown')
            if url:
                output += f"{i}. [{title}]({url}) ({source})\n"
            else:
                output += f"{i}. {title} ({source})\n"
        output += "\n"

    output += "\n> 免責聲明：以上分析僅供參考，不構成投資建議。投資有風險，請謹慎決策。"

    return output


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
            exchange, normalized_symbol = _find_available_exchange(symbol)
            if exchange is None:
                return f"錯誤：無法在支持的交易所中找到 {symbol} 交易對。請確認幣種名稱是否正確。"
        else:
            normalized_symbol = _normalize_symbol(symbol, exchange)

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


# ============================================================================
# 工具列表導出
# ============================================================================

def get_crypto_tools() -> List:
    """獲取所有加密貨幣分析工具"""
    return [
        get_crypto_price_tool,
        technical_analysis_tool,
        news_analysis_tool,
        full_investment_analysis_tool,
    ]


# ============================================================================
# 測試代碼
# ============================================================================

if __name__ == "__main__":
    print("測試工具...")

    # 測試價格查詢
    print("\n=== 測試價格查詢 ===")
    result = get_crypto_price_tool.invoke({"symbol": "BTC"})
    print(result)

    # 測試技術分析
    print("\n=== 測試技術分析 ===")
    result = technical_analysis_tool.invoke({"symbol": "ETH", "interval": "1h"})
    print(result)
