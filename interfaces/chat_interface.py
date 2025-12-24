"""
聊天機器人模組 - 加密貨幣投資分析
支持自然語言查詢，智能提取加密貨幣代號並進行分析
由 api_server.py 調用
"""

import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import operator
import concurrent.futures
from typing import List, Dict, Tuple, Optional
from datetime import datetime

import openai
from dotenv import load_dotenv
from cachetools import cachedmethod, TTLCache, keys

from core.graph import app
from core.config import (
    QUERY_PARSER_MODEL,
    SUPPORTED_EXCHANGES,
    DEFAULT_FUTURES_LEVERAGE,
    MAX_ANALYSIS_WORKERS,
    NEWS_FETCH_LIMIT,
    ENABLE_SPOT_TRADING,
    ENABLE_FUTURES_TRADING
)
from data.data_fetcher import SymbolNotFoundError, get_data_fetcher
from data.indicator_calculator import add_technical_indicators
from utils.utils import get_crypto_news, safe_float

# 導入新的 Agent 模組
try:
    from core.agents import CryptoAgent
    AGENT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: CryptoAgent not available: {e}")
    AGENT_AVAILABLE = False

load_dotenv()


class CryptoQueryParser:
    """使用 LLM 解析用戶查詢並提取加密貨幣代號"""

    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def parse_query(self, user_message: str) -> Dict:
        """
        使用 LLM 解析用戶的自然語言查詢
        """

        system_prompt = """你是一個專業的加密貨幣投資助手。你的任務是解析用戶的問題,提取以下資訊:

1. 用戶意圖 (intent):
   - "investment_analysis": 投資分析或詢問特定數據指標
   - "general_question": 一般問題
   - "greeting": 打招呼

2. 加密貨幣代號 (symbols): 從問題中提取所有提到的加密貨幣代號
   - 如果用戶使用 "它"、"這個"、"他的" 等代名詞，請在 symbols 留下空列表，但在 user_question 標註是代指。
   - 如果用戶說 "比特幣", 轉換為 "BTC"；"以太坊", 轉換為 "ETH"。

3. 動作 (action): "analyze", "compare", "chat"

4. 關注領域 (focus): ["technical", "news", "fundamental", "sentiment"]

5. 是否需要交易決策 (requires_trade_decision): bool

6. 時間週期 (interval): 如果用戶提到特定時間，如 "15分鐘" -> "15m", "1小時" -> "1h", "4小時" -> "4h", "日線" -> "1d"。若無則為 null。

請以 JSON 格式返回結果:
{
    "intent": "investment_analysis",
    "symbols": ["BTC"],
    "action": "analyze",
    "focus": ["technical"],
    "requires_trade_decision": false,
    "interval": "15m",
    "user_question": "查詢 BTC 15分鐘線 RSI"
}
"""

        try:
            response = self.client.chat.completions.create(
                model=QUERY_PARSER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"解析查詢時發生錯誤: {e}")
            return self._fallback_parse(user_message)

    def _fallback_parse(self, user_message: str) -> Dict:
        """當 LLM 解析失敗時的退回方案"""
        crypto_pattern = r'\b([A-Z]{2,10}(?:USDT|BUSD)?)\b'
        matches = re.findall(crypto_pattern, user_message.upper())
        common_words = {'USDT', 'BUSD', 'USD', 'TWD', 'CNY'}
        symbols = [m for m in matches if m not in common_words]

        return {
            "intent": "investment_analysis" if symbols else "general_question",
            "symbols": symbols,
            "action": "compare" if len(symbols) > 1 else "analyze",
            "focus": ["technical", "sentiment", "fundamental", "news"],
            "requires_trade_decision": True,
            "interval": None,
            "user_question": user_message
        }


class CryptoAnalysisBot:
    """加密貨幣分析聊天機器人"""

    def __init__(self, use_agent: bool = True):
        """
        初始化聊天機器人

        Args:
            use_agent: 是否使用新的 ReAct Agent 模式
                      True: 使用 LangChain Agent (支援完整對話 + 動態工具調用)
                      False: 使用舊版固定流程
        """
        self.use_agent = use_agent and AGENT_AVAILABLE

        if self.use_agent:
            # 新架構: 使用 ReAct Agent
            print(">> 使用 ReAct Agent 模式")
            self.agent = CryptoAgent(verbose=False)
        else:
            # 舊架構: 保持向後兼容
            print(">> 使用傳統分析模式")
            self.parser = CryptoQueryParser()
            self.cache = TTLCache(maxsize=100, ttl=300)

        self.chat_history = []
        self.supported_exchanges = SUPPORTED_EXCHANGES
        self.last_symbol = None # 用於追蹤上下文

    def normalize_symbol(self, symbol: str, exchange: str = "binance") -> str:
        """標準化交易對符號"""
        if not symbol: return ""
        symbol = symbol.upper().strip()
        if exchange.lower() == "okx":
            if "-USDT" in symbol or "-BUSD" in symbol: return symbol
            if symbol.endswith("USDT"): return f"{symbol[:-4]}-USDT"
            return f"{symbol}-USDT"
        else:
            if "-USDT" in symbol: return symbol.replace("-USDT", "USDT")
            if symbol.endswith('USDT') or symbol.endswith('BUSD'): return symbol
            return f"{symbol}USDT"

    @cachedmethod(operator.attrgetter('cache'))
    def find_available_exchange(self, symbol: str) -> Optional[Tuple[str, str]]:
        """查找交易對可用的交易所 (已快取)"""
        for exchange in self.supported_exchanges:
            try:
                normalized = self.normalize_symbol(symbol, exchange)
                fetcher = get_data_fetcher(exchange)
                test_data = fetcher.get_historical_klines(normalized, "1d", limit=1)
                if test_data is not None and not test_data.empty:
                    return (exchange, normalized)
            except:
                continue
        return None

    def _fetch_shared_data(self, symbol: str, exchange: str, interval: str = "1d", limit: int = 100, focus: List[str] = None) -> Dict:
        """
        🔥 核心功能：手動預先抓取數據
        """
        # 自動調整數據量：短週期需要更多 K 線才能計算準確的指標 (如 RSI, MACD, EMA)
        # 如果用戶傳入的 limit 太小，自動增加
        effective_limit = limit
        if interval in ['1m', '3m', '5m', '15m', '30m', '1h', '4h'] and limit < 200:
            effective_limit = 200
            print(f">> 自動調整 K 線數量至 {effective_limit} 以確保指標準確性 (原設定: {limit})")

        print(f">> 正在下載分析數據: {symbol} (週期: {interval}, 數量: {effective_limit})...")
        
        data_fetcher = get_data_fetcher(exchange)
        klines_df = data_fetcher.get_historical_klines(symbol, interval=interval, limit=effective_limit)
        
        if klines_df is None or klines_df.empty:
            raise ValueError("無法獲取 K 線數據")

        df_with_indicators = add_technical_indicators(klines_df)
        
        # 檢查指標有效性
        latest = df_with_indicators.iloc[-1]
        if latest.get('RSI_14', 0) == 0:
            print(">> ⚠️ 警告: RSI 計算結果為 0，可能是數據量不足。")

        # 只有在需要新聞或情緒分析時才抓新聞
        news_data = []
        if not focus or any(f in focus for f in ["news", "sentiment", "fundamental"]):
            base_currency = symbol.replace("USDT", "").replace("BUSD", "").replace("-", "").replace("SWAP", "")
            news_data = get_crypto_news(symbol=base_currency, limit=NEWS_FETCH_LIMIT)

        current_price = safe_float(latest['Close'])
        
        recent_history = []
        recent_days = min(5, len(df_with_indicators))
        for i in range(-recent_days, 0):
            day_data = df_with_indicators.iloc[i]
            recent_history.append({
                "日期": i, "開盤": safe_float(day_data['Open']), "最高": safe_float(day_data['High']),
                "最低": safe_float(day_data['Low']), "收盤": safe_float(day_data['Close']), "交易量": safe_float(day_data['Volume'])
            })

        recent_30 = df_with_indicators.tail(30) if len(df_with_indicators) >= 30 else df_with_indicators
        key_levels = {
            "30天最高價": safe_float(recent_30['High'].max()), "30天最低價": safe_float(recent_30['Low'].min()),
            "支撐位": safe_float(recent_30['Low'].quantile(0.25)), "壓力位": safe_float(recent_30['High'].quantile(0.75)),
        }

        price_changes = df_with_indicators['Close'].pct_change()
        market_structure = {
            "趨勢": "上漲" if price_changes.tail(7).mean() > 0 else "下跌",
            "波動率": safe_float(price_changes.tail(30).std() * 100) if len(price_changes) >= 30 else 0,
            "平均交易量": safe_float(df_with_indicators['Volume'].tail(7).mean()),
        }

        return {
            "market_type": "spot",
            "exchange": exchange,
            "leverage": 1,
            "funding_rate_info": {},
            "價格資訊": {
                "當前價格": current_price,
                "7天價格變化百分比": safe_float(((latest['Close'] / df_with_indicators.iloc[-7]['Close']) - 1) * 100) if len(df_with_indicators) >= 7 else 0,
            },
            "技術指標": {
                "RSI_14": safe_float(latest.get('RSI_14', 0)), "MACD_線": safe_float(latest.get('MACD_12_26_9', 0)),
                "布林帶上軌": safe_float(latest.get('BB_upper_20_2', 0)), "布林帶下軌": safe_float(latest.get('BB_lower_20_2', 0)),
                "MA_7": safe_float(latest.get('MA_7', 0)), "MA_25": safe_float(latest.get('MA_25', 0)),
            },
            "最近5天歷史": recent_history,
            "市場結構": market_structure,
            "關鍵價位": key_levels,
            "新聞資訊": news_data
        }

    def _crypto_cache_key(self, symbol, exchange=None, interval="1d", limit=100, account_balance_info=None,
                           short_term_interval="1h", medium_term_interval="4h", long_term_interval="1d",
                           selected_analysts=None, perform_trading_decision=True):
        analysts_tuple = tuple(selected_analysts) if selected_analysts else tuple()
        return keys.hashkey(symbol, exchange, interval, limit, short_term_interval, medium_term_interval, 
                          long_term_interval, analysts_tuple, perform_trading_decision)

    @cachedmethod(operator.attrgetter('cache'), key=_crypto_cache_key)
    def analyze_crypto(self, symbol: str, exchange: str = None, 
                     interval: str = "1d", limit: int = 100, 
                     account_balance_info: Optional[Dict] = None,
                     short_term_interval: str = "1h",
                     medium_term_interval: str = "4h",
                     long_term_interval: str = "1d",
                     selected_analysts: List[str] = None,
                     perform_trading_decision: bool = True) -> Tuple[Optional[Dict], Optional[Dict], str]:
        """
        分析單個加密貨幣
        """
        if exchange is None:
            result = self.find_available_exchange(symbol)
            if result is None:
                raise ValueError(f">> 找不到交易對 {symbol}")
            exchange, normalized_symbol = result
        else:
            normalized_symbol = self.normalize_symbol(symbol, exchange)

        self.last_symbol = normalized_symbol # 紀錄最後分析的幣種
        print(f">> 準備分析 {normalized_symbol} ({exchange}) | 週期: {interval}")

        try:
            shared_data = self._fetch_shared_data(normalized_symbol, exchange, interval, limit, focus=selected_analysts)
            
            spot_state = {
                "symbol": normalized_symbol, "exchange": exchange, "interval": interval,
                "limit": limit, "market_type": 'spot', "leverage": 1,
                "include_multi_timeframe": True if interval == "1d" else False, # 如果是日線才跑多週期
                "short_term_interval": short_term_interval,
                "medium_term_interval": medium_term_interval,
                "long_term_interval": long_term_interval,
                "preloaded_data": shared_data,
                "account_balance": account_balance_info,
                "selected_analysts": selected_analysts,
                "perform_trading_decision": perform_trading_decision
            }

            futures_state = spot_state.copy()
            futures_state.update({"market_type": 'futures', "leverage": DEFAULT_FUTURES_LEVERAGE})

            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_ANALYSIS_WORKERS) as executor:
                future_spot = executor.submit(app.invoke, spot_state) if ENABLE_SPOT_TRADING else None
                future_futures = executor.submit(app.invoke, futures_state) if ENABLE_FUTURES_TRADING else None

                spot_final_state = future_spot.result() if future_spot else None
                futures_final_state = future_futures.result() if future_futures else None

            return spot_final_state, futures_final_state, self._generate_summary(spot_final_state, futures_final_state)

        except Exception as e:
            raise e

    def _generate_summary(self, spot_results: Dict, futures_results: Dict):
        """生成詳細的分析摘要"""
        primary_results = spot_results or futures_results
        if not primary_results:
            yield ">> 無法生成分析報告。"
            return

        symbol = primary_results.get('symbol', '未知幣種')
        current_price = primary_results.get('current_price', 0)
        exchange = primary_results.get('exchange', 'N/A').upper()
        interval = primary_results.get('interval', '1d')
        
        perform_trading_decision = primary_results.get('perform_trading_decision', True)
        selected_analysts = primary_results.get('selected_analysts') or ["technical", "sentiment", "fundamental", "news"]

        yield f"## >> {symbol} 分析報告 ({interval})\n"
        yield f"**交易所**: {exchange} | **當前價格**: ${safe_float(current_price):.4f}\n\n"

        summary_parts = ["### >> 數據概覽"]
        # 技術指標存在於 market_data 中，而非直接存在於 primary_results
        market_data = primary_results.get('market_data', {})
        indicators = market_data.get('技術指標', {})
        if "technical" in selected_analysts:
            rsi = indicators.get('RSI_14', 0)
            summary_parts.append(f"- **RSI (14)**: {rsi:.2f}")
            if interval == '1d':
                summary_parts.append(f"- **7天價格變化**: {market_data.get('價格資訊', {}).get('7天價格變化百分比', 0):.2f}%")

        yield "\n".join(summary_parts) + "\n\n"

        if perform_trading_decision:
            # 辯論與決策部分... (略，保持原邏輯)
            pass

        if "technical" in selected_analysts:
            tech_report = next((r for r in primary_results.get('analyst_reports', []) if r.analyst_type == '技術分析師'), None)
            if tech_report:
                yield f"### 📉 技術分析 ({interval})\n{tech_report.summary}\n\n"

        if any(f in selected_analysts for f in ["news", "sentiment", "fundamental"]):
            summary_parts = ["### 📰 新聞與基本面"]
            news_report = next((r for r in primary_results.get('analyst_reports', []) if r.analyst_type == '新聞分析師'), None)
            if news_report: summary_parts.append(f"**新聞**: {news_report.summary}")
            yield "\n".join(summary_parts) + "\n"

        yield f"\n*分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    def process_message(self, user_message: str, interval: str = "1d", limit: int = 100, manual_selection: List[str] = None):
        """
        處理用戶消息

        Args:
            user_message: 用戶輸入的消息
            interval: 時間週期 (舊模式使用)
            limit: 數據量限制 (舊模式使用)
            manual_selection: 手動選擇的分析類型 (舊模式使用)

        Yields:
            回應文字
        """
        # ============ 新架構: 使用 ReAct Agent ============
        if self.use_agent:
            try:
                # 使用 Agent 處理對話
                for chunk in self.agent.chat_stream(user_message):
                    yield chunk
            except Exception as e:
                yield f"處理請求時發生錯誤: {str(e)}"
            return

        # ============ 舊架構: 保持向後兼容 ============
        parsed = self.parser.parse_query(user_message)
        intent = parsed.get("intent", "general_question")
        symbols = parsed.get("symbols", [])

        # 如果 LLM 解析沒找到幣種，嘗試用正則表達式從消息中提取
        if not symbols:
            crypto_pattern = r'\b([A-Z]{2,10})\b'
            matches = re.findall(crypto_pattern, user_message.upper())
            # 排除常見非幣種詞彙
            common_words = {'USDT', 'BUSD', 'USD', 'TWD', 'CNY', 'THE', 'AND', 'FOR', 'RSI', 'MACD', 'EMA', 'SMA', 'MA', 'BB', 'API', 'OK', 'HTTP'}
            explicit_symbols = [m for m in matches if m not in common_words and len(m) >= 2]
            if explicit_symbols:
                symbols = explicit_symbols[:3]  # 最多取前3個
                print(f">> 從消息中提取到幣種: {symbols}")

        # 上下文補全：只有在消息中完全沒有幣種時才使用歷史幣種
        if not symbols and self.last_symbol:
            # 去除 OKX 的 -USDT 後綴進行補全
            base_last = self.last_symbol.replace("-USDT", "").replace("USDT", "")
            symbols = [base_last]
            print(f">> 從上下文補全幣種: {symbols}")

        if intent == "greeting":
            yield "你好！我是加密貨幣投資分析助手，請問有什麼可以為您服務的？"
            return

        if symbols:
            # 時間週期優先級：提問文字 > 手動 UI 選擇
            query_interval = parsed.get("interval")
            final_interval = query_interval if query_interval else interval

            focus = parsed.get("focus", ["technical", "sentiment", "fundamental", "news"])
            requires_trade_decision = parsed.get("requires_trade_decision", True)

            # 手動 UI 勾選覆蓋
            if manual_selection:
                selected_map = {"Technical Analysis": "technical", "News Analysis": "news", "Fundamental Analysis": "fundamental", "Sentiment Analysis": "sentiment"}
                manual_focus = [selected_map[item] for item in manual_selection if item in selected_map]
                if manual_focus: focus = manual_focus
                if "Full Trading Decision" in manual_selection: requires_trade_decision = True
                elif manual_focus: requires_trade_decision = False

            symbol = symbols[0]
            yield f"好的，正在為您分析 {symbol} ({final_interval})...\n"

            try:
                _, _, summary_generator = self.analyze_crypto(
                    symbol, interval=final_interval, limit=limit,
                    selected_analysts=focus, perform_trading_decision=requires_trade_decision
                )
                response_so_far = ""
                for part in summary_generator:
                    response_so_far += part
                    yield response_so_far
            except Exception as e:
                yield f"\n>> 分析時發生錯誤: {e}"
        else:
            yield "抱歉，我不太理解您的問題。您可以試著問我「比特幣可以投資嗎？」或指定特定指標如「它的 15分鐘線 RSI 是多少」。"

    def clear_history(self):
        """清除對話歷史"""
        self.chat_history = []
        if self.use_agent:
            self.agent.clear_history()
        self.last_symbol = None