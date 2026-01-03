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
import json
import time

import openai
from dotenv import load_dotenv
from cachetools import cachedmethod, TTLCache, keys

from core.graph import app
from core.tools import format_full_analysis_result
from core.config import (
    QUERY_PARSER_MODEL_CONFIG,
    SUPPORTED_EXCHANGES,
    DEFAULT_FUTURES_LEVERAGE,
    MAX_ANALYSIS_WORKERS,
    NEWS_FETCH_LIMIT,
    ENABLE_SPOT_TRADING,
    ENABLE_FUTURES_TRADING,
    DEFAULT_KLINES_LIMIT,
    DEFAULT_INTERVAL
)
from data.data_fetcher import SymbolNotFoundError, get_data_fetcher
from data.indicator_calculator import add_technical_indicators
from utils.utils import get_crypto_news, safe_float
from utils.llm_client import create_llm_client_from_config

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
        """初始化 CryptoQueryParser，使用統一的 LLM 客戶端工廠"""
        self.client, self.model = create_llm_client_from_config(QUERY_PARSER_MODEL_CONFIG)

    def parse_query(self, user_message: str) -> Dict:
        """
        使用 LLM 解析用戶的自然語言查詢
        """

        system_prompt = """你是一個專業的加密貨幣投資助手。你的任務是解析用戶的問題,提取以下資訊:

1. 用戶意圖 (intent):
   - "investment_analysis": 當用戶詢問任何與投資、交易、買賣、價格分析相關的問題時使用。
     包括但不限於：
     * "XXX 可以投資嗎？" / "XXX 能買嗎？" / "XXX 適合買入嗎？"
     * "XXX 怎麼樣？" / "XXX 如何？" / "XXX 現在好嗎？"
     * "分析 XXX" / "幫我看看 XXX" / "XXX 的走勢"
     * "XXX 值得買嗎？" / "應該買 XXX 嗎？"
     * 任何提到加密貨幣名稱並詢問意見或分析的問題
   - "general_question": 純粹的知識性問題，不涉及具體投資決策（如 "什麼是區塊鏈？"）
   - "greeting": 打招呼
   - "unclear": 意圖不明確，需要澄清

2. 加密貨幣代號 (symbols): 從問題中提取所有提到的加密貨幣代號
   - 如果用戶使用 "它"、"這個"、"他的" 等代名詞，請在 symbols 留下空列表，但在 user_question 標註是代指。
   - 常見轉換：比特幣->BTC, 以太坊->ETH, 狗狗幣->DOGE, 瑞波幣->XRP, 萊特幣->LTC, 柚子幣->EOS, 派幣->PI

3. 動作 (action): "analyze", "compare", "chat"

4. 關注領域 (focus): ["technical", "news", "fundamental", "sentiment"]

5. 是否需要交易決策 (requires_trade_decision): bool
   **重要**: 當 intent 為 "investment_analysis" 且用戶詢問的是投資建議、買賣時機、是否適合投資等問題時，必須設為 true。
   只有在用戶明確表示只想看某個特定指標（如 "只看 RSI"）時才設為 false。

6. 時間週期 (interval): 如果用戶提到特定時間，如 "15分鐘" -> "15m", "1小時" -> "1h", "4小時" -> "4h", "日線" -> "1d"。若無則為 null。

7. 意圖清晰度 (clarity): "high" / "medium" / "low"

8. 澄清問題 (clarification_question): 如果 clarity 為 "low"，提供一個澄清問題

9. 建議選項 (suggested_options): 如果 clarity 為 "low"，提供 2-4 個可能的選項

範例：
用戶: "BTC可以投資嗎？"
{
    "intent": "investment_analysis",
    "symbols": ["BTC"],
    "action": "analyze",
    "focus": ["technical", "sentiment", "fundamental", "news"],
    "requires_trade_decision": true,
    "interval": null,
    "user_question": "BTC可以投資嗎？",
    "clarity": "high",
    "clarification_question": null,
    "suggested_options": null
}

用戶: "幫我分析一下以太坊"
{
    "intent": "investment_analysis",
    "symbols": ["ETH"],
    "action": "analyze",
    "focus": ["technical", "sentiment", "fundamental", "news"],
    "requires_trade_decision": true,
    "interval": null,
    "user_question": "幫我分析一下以太坊",
    "clarity": "high",
    "clarification_question": null,
    "suggested_options": null
}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
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
        common_words = {'USDT', 'BUSD', 'USD', 'TWD', 'CNY', 'THE', 'AND', 'FOR', 'ARE', 'NOT'}
        symbols = [m for m in matches if m not in common_words]

        # 如果沒有找到任何幣種，標記為不明確
        if not symbols and len(user_message) < 10:
            return {
                "intent": "unclear",
                "symbols": [],
                "action": "chat",
                "focus": [],
                "requires_trade_decision": False,
                "interval": None,
                "user_question": user_message,
                "clarity": "low",
                "clarification_question": "請問您想要分析哪個加密貨幣？或者有什麼我可以幫助您的？",
                "suggested_options": [
                    "分析 BTC (比特幣)",
                    "分析 ETH (以太坊)",
                    "查看市場熱門幣種",
                    "詢問加密貨幣相關問題"
                ]
            }

        return {
            "intent": "investment_analysis" if symbols else "general_question",
            "symbols": symbols,
            "action": "compare" if len(symbols) > 1 else "analyze",
            "focus": ["technical", "sentiment", "fundamental", "news"],
            "requires_trade_decision": True,
            "interval": None,
            "user_question": user_message,
            "clarity": "high" if symbols else "medium",
            "clarification_question": None,
            "suggested_options": None
        }


def _crypto_cache_key(self, symbol, exchange=None, interval="1d", limit=100, account_balance_info=None,
                       short_term_interval="1h", medium_term_interval="4h", long_term_interval="1d",
                       selected_analysts=None, perform_trading_decision=True):
    """快取鍵生成函數 - 必須在類別外部定義以供裝飾器使用"""
    analysts_tuple = tuple(selected_analysts) if selected_analysts else tuple()
    return keys.hashkey(symbol, exchange, interval, limit, short_term_interval, medium_term_interval,
                        long_term_interval, analysts_tuple, perform_trading_decision)


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

        # 始終初始化解析器，用於混合模式判斷
        self.parser = CryptoQueryParser()

        # 始終初始化快取 (用於 find_available_exchange 等方法)
        self.cache = TTLCache(maxsize=100, ttl=300)

        if self.use_agent:
            # 新架構: 使用 ReAct Agent
            print(">> 使用 ReAct Agent 模式 (混合串流增強)")
            self.agent = CryptoAgent(verbose=False)
        else:
            # 舊架構: 保持向後兼容
            print(">> 使用傳統分析模式")

        self.chat_history = []
        self.supported_exchanges = SUPPORTED_EXCHANGES
        self.last_symbol = None # 用於追蹤上下文

    def normalize_symbol(self, symbol: str, exchange: str = "binance") -> str:
        """標準化交易對符號"""
        if not symbol: return ""
        symbol = symbol.upper().strip()
        
        # 1. 先提取基礎幣種 (Base Currency)
        base_symbol = symbol.replace("-", "").replace("_", "")
        
        if base_symbol.endswith("USDT"):
            base_symbol = base_symbol[:-4]
        elif base_symbol.endswith("BUSD"):
            base_symbol = base_symbol[:-4]
        elif base_symbol.endswith("USD"):
            base_symbol = base_symbol[:-3]

        # 2. 根據交易所格式化
        if exchange.lower() == "okx":
            return f"{base_symbol}-USDT"
        else:  # binance
            return f"{base_symbol}USDT"

    @cachedmethod(operator.attrgetter('cache') if not hasattr(operator.attrgetter('cache'), 'use_agent') else lambda x: x.cache, key=_crypto_cache_key)
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
            print(">> ⚠️ 警告: RSI 計算結果為 0，可能是數據量不足。" )

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

    @cachedmethod(operator.attrgetter('cache') if not hasattr(operator.attrgetter('cache'), 'use_agent') else lambda x: x.cache, key=_crypto_cache_key)
    def analyze_crypto(self, symbol: str, exchange: str = None, 
                     interval: str = "1d", limit: int = 100, 
                     account_balance_info: Optional[Dict] = None,
                     short_term_interval: str = "1h",
                     medium_term_interval: str = "4h",
                     long_term_interval: str = "1d",
                     selected_analysts: List[str] = None,
                     perform_trading_decision: bool = True) -> Tuple[Optional[Dict], Optional[Dict], str]:
        """
        分析單個加密貨幣 (舊模式)
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
    
    def process_message(self, user_message: str, interval: str = "1d", limit: int = 100,
                       manual_selection: List[str] = None, auto_execute: bool = False,
                       market_type: str = "spot", user_llm_client=None, user_provider: str = "openai"):
        """
        處理用戶消息 (支援混合模式：普通問題走 Agent，完整分析走即時串流 Graph)

        Args:
            user_llm_client: ⭐ 用戶提供的 LLM 客戶端
            user_provider: ⭐ 用戶選擇的 provider
        """
        def simulate_stream(text: str, prefix: str = "", delay: float = 0.01, chunk_size: int = 10):
            """模擬打字機流式輸出"""
            if prefix:
                yield prefix
            for i in range(0, len(text), chunk_size):
                yield text[i:i+chunk_size]
                time.sleep(delay)
            yield "\n\n"

        # 1. 嘗試解析意圖
        try:
            parsed = self.parser.parse_query(user_message)
            if not parsed:
                parsed = {} # Fallback to empty dict to avoid NoneType error
            
            intent = parsed.get("intent", "general_question")
            symbols = parsed.get("symbols", [])
            requires_trade_decision = parsed.get("requires_trade_decision", False)
            clarity = parsed.get("clarity", "high")
            clarification_question = parsed.get("clarification_question")
            suggested_options = parsed.get("suggested_options", [])

            # 處理意圖不明確的情況
            if clarity == "low" or intent == "unclear":
                yield "🤔 **我不太確定您的意思，讓我確認一下：**\n\n"
                if clarification_question:
                    yield f"❓ {clarification_question}\n\n"
                if suggested_options:
                    yield "您可以試試以下選項：\n"
                    for i, option in enumerate(suggested_options, 1):
                        yield f"  {i}. {option}\n"
                    yield "\n"
                yield "請告訴我您想要什麼，我會盡力幫助您！\n"
                return

            # 上下文補全
            if not symbols and self.last_symbol:
                 if any(w in user_message for w in ["它", "這個", "繼續", "分析"]):
                     base_last = self.last_symbol.replace("-USDT", "").replace("USDT", "")
                     symbols = [base_last]

            # 2. 判斷是否觸發「完整投資分析直通車」
            print(f"[DEBUG] intent={intent}, requires_trade_decision={requires_trade_decision}, symbols={symbols}")
            if intent == "investment_analysis" and requires_trade_decision and symbols:
                symbol = symbols[0]
                print(f"[DEBUG] 進入完整分析流程: {symbol}")
                # 開始過程區塊 - 必須在所有 [PROCESS] 訊息之前發送
                yield "[PROCESS_START]\n"
                yield f"[PROCESS]🚀 正在為您啟動 {symbol} 的深度全方位分析...\n"

                try:
                    yield f"[PROCESS]🔍 正在查找交易所...\n"
                    exchange_info = self.find_available_exchange(symbol)
                except Exception as e:
                    yield f"[PROCESS]❌ 查找交易所時出錯: {str(e)}\n"
                    return

                if not exchange_info:
                    yield f"⚠️ 找不到 {symbol} 的相關交易對，請確認名稱。\n"
                    return

                exchange, normalized_symbol = exchange_info
                
                # 如果是合約市場且交易所是 OKX，確保符號正確 (OKX 合約格式: BTC-USDT-SWAP)
                if market_type == "futures" and exchange == "okx" and not normalized_symbol.endswith("-SWAP"):
                    normalized_symbol = normalized_symbol + "-SWAP"
                
                self.last_symbol = normalized_symbol
                yield f"[PROCESS]✅ 找到交易對: {normalized_symbol} @ {exchange} ({'現貨' if market_type == 'spot' else '合約'})\n"

                # 嘗試獲取帳戶餘額 (用於計算建議倉位，無論是否自動執行)
                account_balance = None
                from trading.okx_api_connector import OKXAPIConnector
                okx = OKXAPIConnector()
                
                # 只有當 Key 存在時才嘗試獲取餘額
                if all([okx.api_key, okx.secret_key, okx.passphrase]):
                    try:
                        # 獲取 USDT 餘額
                        bal_res = okx.get_account_balance("USDT")
                        if bal_res and bal_res.get('code') == '0' and bal_res.get('data'):
                            details = bal_res['data'][0]['details']
                            usdt_bal = next((d for d in details if d['ccy'] == 'USDT'), None)
                            if usdt_bal:
                                avail = float(usdt_bal.get('availBal', 0))
                                account_balance = {'available_balance': avail, 'currency': 'USDT'}
                                yield f"[PROCESS]💳 帳戶餘額: ${avail:.2f} USDT\n"
                    except Exception as e:
                        # 靜默失敗，不阻擋分析流程，只影響後續金額計算
                        print(f"Failed to fetch balance: {e}")
                
                # 如果開啟自動交易但沒有 Key，發出警告
                if auto_execute and not account_balance:
                     if not all([okx.api_key, okx.secret_key, okx.passphrase]):
                        yield f"[PROCESS]⚠️ **警告**: 您啟用了自動交易，但尚未設定 API Key。\n"
                        auto_execute = False
                     else:
                        yield f"[PROCESS]⚠️ **警告**: 無法獲取餘額，自動交易可能受限。\n"

                state_input = {
                    "symbol": normalized_symbol,
                    "exchange": exchange,
                    "interval": parsed.get("interval") or interval,
                    "limit": DEFAULT_KLINES_LIMIT,
                    "market_type": market_type,
                    "leverage": 1 if market_type == "spot" else 5, # 預設合約 5 倍
                    "include_multi_timeframe": True,
                    "short_term_interval": "1h",
                    "medium_term_interval": "4h",
                    "long_term_interval": "1d",
                    "preloaded_data": None,
                    "account_balance": account_balance,
                    "selected_analysts": parsed.get("focus") or ["technical", "sentiment", "fundamental", "news"],
                    "perform_trading_decision": True,
                    "execute_trade": False, # 禁用圖表內自動執行，改為前端手動確認 (HITL)
                    "debate_round": 0,
                    "debate_history": [],
                    # ⭐ 添加用戶的 LLM client
                    "user_llm_client": user_llm_client,
                    "user_provider": user_provider
                }

                try:
                    accumulated_state = state_input.copy()
                    yield f"[PROCESS]⏳ 開始執行分析流程...\n"

                    event_count = 0
                    for event in app.stream(state_input):
                        event_count += 1
                        for node_name, state_update in event.items():
                            accumulated_state.update(state_update)

                            if node_name == "prepare_data":
                                price = state_update.get("current_price", 0)
                                yield f"[PROCESS]✅ **數據準備完成**: 當前價格 ${price:.4f}\n"

                            elif node_name == "run_analyst_team":
                                reports = state_update.get("analyst_reports", [])
                                yield f"[PROCESS]📊 **AI 分析師團隊**: 已完成 {len(reports)} 份專業報告\n"
                                for report in reports:
                                    analyst_type = getattr(report, 'analyst_type', '分析師')
                                    bullish = len(getattr(report, 'bullish_points', []))
                                    bearish = len(getattr(report, 'bearish_points', []))
                                    total = bullish + bearish
                                    if total > 0:
                                        # 用視覺化比例條顯示多空比
                                        bull_ratio = bullish / total
                                        bull_bars = round(bull_ratio * 5)
                                        bear_bars = 5 - bull_bars
                                        bar = '🟩' * bull_bars + '🟥' * bear_bars
                                        signal = f"{bar} ({bullish}多/{bearish}空)"
                                    else:
                                        signal = "⬜⬜⬜⬜⬜ (無數據)"
                                    yield f"[PROCESS]   → {analyst_type}: {signal}\n"

                            elif node_name == "run_research_debate":
                                history = accumulated_state.get("debate_history", [])
                                if history:
                                    latest = history[-1]
                                    yield f"[PROCESS]\n---\n### ⚔️ 第 {latest.get('round')} 輪辯論：{latest.get('topic')}\n\n"
                                    
                                    # --- 多頭展示 ---
                                    bull_arg = latest.get('bull', {}).get('argument', '無觀點')
                                    bull_details = latest.get('bull_committee_details', [])
                                    
                                    if bull_details:
                                        yield f"[PROCESS]**🐂 多頭委員會 (共識觀點)**:\n> {bull_arg.replace(chr(10), chr(10) + '> ')}\n"
                                        yield f"[PROCESS]   🔻 委員會成員觀點:\n"
                                        for i, member in enumerate(bull_details):
                                            m_arg = member.get('argument', '無內容')
                                            # 只取前 150 字作為摘要，避免過長
                                            summary = m_arg[:150].replace('\n', ' ') + "..." if len(m_arg) > 150 else m_arg
                                            yield f"[PROCESS]   🔸 成員 {i+1}: {summary}\n"
                                        yield f"[PROCESS]\n"
                                    else:
                                        yield f"[PROCESS]**🐂 多頭觀點**:\n> {bull_arg.replace(chr(10), chr(10) + '> ')}\n\n"

                                    # --- 空頭展示 ---
                                    bear_arg = latest.get('bear', {}).get('argument', '無觀點')
                                    bear_details = latest.get('bear_committee_details', [])
                                    
                                    if bear_details:
                                        yield f"[PROCESS]**🐻 空頭委員會 (共識觀點)**:\n> {bear_arg.replace(chr(10), chr(10) + '> ')}\n"
                                        yield f"[PROCESS]   🔻 委員會成員觀點:\n"
                                        for i, member in enumerate(bear_details):
                                            m_arg = member.get('argument', '無內容')
                                            summary = m_arg[:150].replace('\n', ' ') + "..." if len(m_arg) > 150 else m_arg
                                            yield f"[PROCESS]   🔸 成員 {i+1}: {summary}\n"
                                        yield f"[PROCESS]\n"
                                    else:
                                        yield f"[PROCESS]**🐻 空頭觀點**:\n> {bear_arg.replace(chr(10), chr(10) + '> ')}\n\n"

                                    # --- 中立展示 ---
                                    neutral_arg = latest.get('neutral', {}).get('argument', '無觀點')
                                    yield f"[PROCESS]**⚖️ 中立觀點**:\n> {neutral_arg.replace(chr(10), chr(10) + '> ')}\n\n"

                            elif node_name == "run_debate_judgment":
                                judgment = state_update.get("debate_judgment")
                                if judgment:
                                    winner = judgment.winning_stance
                                    action = judgment.suggested_action
                                    yield f"[PROCESS]👨‍⚖️ **辯論裁決**: 勝方 **{winner}** → 建議 **{action}**\n"
                                    yield f"[PROCESS]   🐂 多頭評估: {judgment.bull_evaluation}\n"
                                    yield f"[PROCESS]   🐻 空頭評估: {judgment.bear_evaluation}\n"
                                    yield f"[PROCESS]   ⚖️ 中立評估: {judgment.neutral_evaluation}\n"
                                    yield f"[PROCESS]   💪 多頭最強論點: {judgment.strongest_bull_point}\n"
                                    yield f"[PROCESS]   💪 空頭最強論點: {judgment.strongest_bear_point}\n"
                                    if judgment.fatal_flaw:
                                        yield f"[PROCESS]   ⚠️ 致命缺陷: {judgment.fatal_flaw}\n"
                                    yield f"[PROCESS]   🏆 獲勝原因: {judgment.winning_reason}\n"
                                    yield f"[PROCESS]   📝 行動依據: {judgment.action_rationale}\n"
                                    yield f"[PROCESS]   📌 {judgment.key_takeaway}\n\n"

                            elif node_name == "run_trader_decision":
                                decision = state_update.get("trader_decision")
                                follows = "✅ 遵循裁判" if decision.follows_judge else "⚠️ 偏離裁判"
                                yield f"[PROCESS]⚖️ **交易員決策**: **{decision.decision}** | 倉位: {decision.position_size:.0%} | {follows}\n"
                                if decision.reasoning:
                                    yield f"[PROCESS]   💭 決策理由: {decision.reasoning}\n"
                                if not decision.follows_judge and decision.deviation_reason:
                                    yield f"[PROCESS]   偏離原因: {decision.deviation_reason}\n"
                                yield f"[PROCESS]   主要風險: {decision.key_risk}\n"

                            elif node_name == "run_risk_management":
                                risk = state_update.get("risk_assessment")
                                yield f"[PROCESS]🛡️ **風險評估**: {risk.risk_level} (批准狀態: {'✅ 通過' if risk.approve else '❌ 不通過'})\n"
                                yield f"[PROCESS]   📋 評估內容: {risk.assessment}\n"
                                if risk.warnings:
                                    yield f"[PROCESS]   ⚠️ 風險警告: {'; '.join(risk.warnings)}\n"
                                yield f"[PROCESS]   💡 建議調整: {risk.suggested_adjustments}\n"
                                yield f"[PROCESS]   📊 調整後倉位: {risk.adjusted_position_size:.0%}\n"

                            elif node_name == "run_fund_manager_approval":
                                approval = state_update.get("final_approval")
                                yield f"[PROCESS]💰 **基金經理最終審批**: {approval.final_decision}\n"
                                yield f"[PROCESS]   📝 審批理由: {approval.rationale}\n"
                                yield f"[PROCESS]   📊 最終倉位: {approval.final_position_size:.0%}\n"
                                if approval.execution_notes:
                                    yield f"[PROCESS]   📋 執行備註: {approval.execution_notes}\n"
                                
                                # HITL: 如果獲得批准，生成交易提案供前端顯示
                                if approval.approved:
                                    # 提取交易決策細節
                                    decision = accumulated_state.get('trader_decision')
                                    market_type = accumulated_state.get('market_type')
                                    symbol = accumulated_state.get('symbol')
                                    leverage = approval.approved_leverage or 1
                                    
                                    # 計算建議金額 (基於倉位與餘額)
                                    balance = accumulated_state.get('account_balance')
                                    amount = 0
                                    balance_status = "unknown"

                                    if balance:
                                        avail = balance.get('available_balance', 0)
                                        if avail > 0:
                                            amount = avail * approval.final_position_size
                                            balance_status = "ok"
                                        else:
                                            balance_status = "zero"
                                    
                                    proposal = {
                                        "symbol": symbol,
                                        "market_type": market_type,
                                        "side": "buy" if "Buy" in decision.decision else ("long" if "Long" in decision.decision else "short"),
                                        "amount": round(amount, 2),
                                        "leverage": leverage,
                                        "price": decision.entry_price,
                                        "stop_loss": decision.stop_loss,
                                        "take_profit": decision.take_profit,
                                        "balance_status": balance_status
                                    }
                                    
                                    # 改為嵌入式按鈕數據，而非自動彈窗
                                    # 我們使用一個特殊的隱藏區塊，讓前端解析並渲染按鈕
                                    proposal_json = json.dumps(proposal)
                                    yield f"\n\n<!-- TRADE_PROPOSAL_START {proposal_json} TRADE_PROPOSAL_END -->\n"

                    # 結束過程區塊
                    yield "[PROCESS_END]\n"

                    # 最終報告
                    yield "[RESULT]\n"
                    formatted_report = format_full_analysis_result(accumulated_state, "現貨", normalized_symbol, accumulated_state['interval'])
                    yield formatted_report
                    return

                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"❌ 分析過程中發生錯誤: {error_detail}")
                    yield f"[PROCESS]❌ 分析過程中發生錯誤: {str(e)}\n"
                    yield "[PROCESS_END]\n"
                    yield f"[RESULT]\n❌ **錯誤**: {str(e)}\n\n請檢查後端日誌以獲取更多詳情。"
                    return

        except Exception as e:
            print(f"解析意圖失敗: {e}")

        if self.use_agent:
            try:
                for chunk in self.agent.chat_stream(user_message):
                    yield chunk
            except Exception as e:
                yield f"處理請求時發生錯誤: {str(e)}"
            return

        yield "抱歉，我不太理解您的問題。"

    def clear_history(self):
        """清除對話歷史"""
        self.chat_history = []
        if self.use_agent:
            self.agent.clear_history()
        self.last_symbol = None