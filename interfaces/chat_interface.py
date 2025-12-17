"""
聊天界面模組 - 使用 Gradio 創建對話式加密貨幣投資分析界面
支持自然語言查詢，智能提取加密貨幣代號並進行分析
"""

import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
import re
from typing import List, Dict, Tuple, Optional
import openai
from dotenv import load_dotenv
from core.graph import app
from data.data_fetcher import SymbolNotFoundError, get_data_fetcher
import json
from datetime import datetime
from data.data_fetcher import get_data_fetcher
from utils.utils import get_crypto_news, safe_float
from data.indicator_calculator import add_technical_indicators
import concurrent.futures  # <--- 記得加在文件最上面
from analysis.crypto_screener import screen_top_cryptos
import pandas as pd
from cachetools import cachedmethod, TTLCache # <--- 引入快取工具
import operator  # <--- 用於 cachedmethod
# 引入中心化配置
from core.config import (
    QUERY_PARSER_MODEL,
    SUPPORTED_EXCHANGES,
    DEFAULT_FUTURES_LEVERAGE,
    MAX_ANALYSIS_WORKERS,
    DEFAULT_INTERVAL,
    DEFAULT_KLINES_LIMIT,
    SCREENER_DEFAULT_LIMIT,
    SCREENER_DEFAULT_INTERVAL
)

load_dotenv()


class CryptoQueryParser:
    """使用 LLM 解析用戶查詢並提取加密貨幣代號"""

    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def parse_query(self, user_message: str) -> Dict:
        """
        使用 LLM 解析用戶的自然語言查詢

        Args:
            user_message: 用戶的問題

        Returns:
            Dict: {
                "intent": "investment_analysis",  # 意圖
                "symbols": ["BTC", "ETH"],  # 提取的加密貨幣代號
                "action": "analyze"  # 動作
            }
        """

        system_prompt = """你是一個專業的加密貨幣投資助手。你的任務是解析用戶的問題,提取以下資訊:

1. 用戶意圖 (intent):
   - "investment_analysis": 投資分析
   - "general_question": 一般問題
   - "greeting": 打招呼

2. 加密貨幣代號 (symbols): 從問題中提取所有提到的加密貨幣代號
   - 常見格式: BTC, ETH, XRP, PI, PIUSDT, BTCUSDT 等
   - 注意: PI 代表 Pi Network
   - 如果用戶說 "比特幣", 轉換為 "BTC"
   - 如果用戶說 "以太坊", 轉換為 "ETH"
   - 如果已經包含 USDT 後綴(如 PIUSDT), 保持原樣
   - 如果沒有 USDT 後綴, 不要自動添加

3. 動作 (action):
   - "analyze": 進行投資分析
   - "compare": 比較多個幣種
   - "chat": 普通對話

請以 JSON 格式返回結果:
{
    "intent": "investment_analysis",
    "symbols": ["BTC", "ETH"],
    "action": "analyze",
    "user_question": "用戶的原始問題摘要"
}

範例:
- 輸入: "PI 可以投資嗎?"
  輸出: {"intent": "investment_analysis", "symbols": ["PI"], "action": "analyze", "user_question": "PI 是否可以投資"}

- 輸入: "PIUSDT 可以投資嘛"
  輸出: {"intent": "investment_analysis", "symbols": ["PIUSDT"], "action": "analyze", "user_question": "PIUSDT 是否可以投資"}

- 輸入: "XRP, PI, ETH 哪些可以投資"
  輸出: {"intent": "investment_analysis", "symbols": ["XRP", "PI", "ETH"], "action": "compare", "user_question": "比較 XRP, PI, ETH 的投資價值"}

- 輸入: "比特幣最近表現如何"
  輸出: {"intent": "investment_analysis", "symbols": ["BTC"], "action": "analyze", "user_question": "比特幣最近的表現"}
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
            # 退回到簡單的正則表達式提取
            return self._fallback_parse(user_message)

    def _fallback_parse(self, user_message: str) -> Dict:
        """當 LLM 解析失敗時的退回方案"""
        # 使用正則表達式提取常見的加密貨幣代號
        crypto_pattern = r'\b([A-Z]{2,10}(?:USDT|BUSD)?)\b'
        matches = re.findall(crypto_pattern, user_message.upper())

        # 過濾常見詞彙
        common_words = {'USDT', 'BUSD', 'USD', 'TWD', 'CNY'}
        symbols = [m for m in matches if m not in common_words]

        return {
            "intent": "investment_analysis" if symbols else "general_question",
            "symbols": symbols,
            "action": "compare" if len(symbols) > 1 else "analyze",
            "user_question": user_message
        }


class CryptoAnalysisBot:
    """加密貨幣分析聊天機器人"""

    def __init__(self):
        self.parser = CryptoQueryParser()
        # 建議：安裝 cachetools -> pip install cachetools
        self.cache = TTLCache(maxsize=100, ttl=300) # 快取 100 筆，每筆存活 5 分鐘
        self.chat_history = []
        # 從中心化配置讀取支持的交易所
        self.supported_exchanges = SUPPORTED_EXCHANGES

    def normalize_symbol(self, symbol: str, exchange: str = "binance") -> str:
        """標準化交易對符號"""
        symbol = symbol.upper().strip()
        if exchange.lower() == "okx":
            if "-USDT" in symbol or "-BUSD" in symbol: return symbol
            if symbol.endswith("USDT"): return f"{symbol[:-4]}-USDT"
            if symbol.endswith("BUSD"): return f"{symbol[:-4]}-BUSD"
            return f"{symbol}-USDT"
        else:
            if "-USDT" in symbol: return symbol.replace("-USDT", "USDT")
            if "-BUSD" in symbol: return symbol.replace("-BUSD", "BUSD")
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
                    print(f">> 在 {exchange.upper()} 找到交易對: {normalized}")
                    return (exchange, normalized)
            except:
                continue
        return None

    def _fetch_shared_data(self, symbol: str, exchange: str, interval: str = "1d", limit: int = 100) -> Dict:
        """
        🔥 核心功能：手動預先抓取數據 (只抓一次，供兩邊使用)
        這段邏輯是從 graph.py 的 prepare_data_node 提取出來的
        """
        print(f">> 正在預先下載共用數據: {symbol}...")
        
        # 1. 獲取數據抓取器
        data_fetcher = get_data_fetcher(exchange)
        
        # 2. 為了節省資源，我們統一抓取「現貨 Spot」數據作為分析基礎
        # (雖然合約價格略有不同，但技術指標趨勢是一致的)
        klines_df = data_fetcher.get_historical_klines(symbol, interval=interval, limit=limit)
        
        if klines_df is None or klines_df.empty:
            raise ValueError("無法獲取 K 線數據")

        # 3. 添加技術指標
        df_with_indicators = add_technical_indicators(klines_df)
        
        # 4. 抓取新聞
        base_currency = symbol.replace("USDT", "").replace("BUSD", "").replace("-", "").replace("SWAP", "")
        news_data = get_crypto_news(symbol=base_currency, limit=5)

        # 5. 整理數據結構 (這必須跟 AgentState 要求的格式一樣)
        latest = df_with_indicators.iloc[-1]
        current_price = safe_float(latest['Close'])
        
        # 最近5天歷史
        recent_history = []
        recent_days = min(5, len(df_with_indicators))
        for i in range(-recent_days, 0):
            day_data = df_with_indicators.iloc[i]
            recent_history.append({
                "日期": i, "開盤": safe_float(day_data['Open']), "最高": safe_float(day_data['High']),
                "最低": safe_float(day_data['Low']), "收盤": safe_float(day_data['Close']), "交易量": safe_float(day_data['Volume'])
            })

        # 關鍵價位
        recent_30 = df_with_indicators.tail(30) if len(df_with_indicators) >= 30 else df_with_indicators
        key_levels = {
            "30天最高價": safe_float(recent_30['High'].max()), "30天最低價": safe_float(recent_30['Low'].min()),
            "支撐位": safe_float(recent_30['Low'].quantile(0.25)), "壓力位": safe_float(recent_30['High'].quantile(0.75)),
        }

        # 市場結構
        price_changes = df_with_indicators['Close'].pct_change()
        market_structure = {
            "趨勢": "上漲" if price_changes.tail(7).mean() > 0 else "下跌",
            "波動率": safe_float(price_changes.tail(30).std() * 100) if len(price_changes) >= 30 else 0,
            "平均交易量": safe_float(df_with_indicators['Volume'].tail(7).mean()),
        }

        # 返回共用數據包
        return {
            "market_type": "spot", # 這裡先標記為 spot，傳入 graph 後會被覆蓋
            "exchange": exchange,
            "leverage": 1,
            "funding_rate_info": {}, # 共用數據暫不包含合約特定的資金費率
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

    @cachedmethod(operator.attrgetter('cache'))
    def analyze_crypto(self, symbol: str, exchange: str = None, interval: str = "1d", limit: int = 100) -> Tuple[Optional[Dict], Optional[Dict], str]:
        """
        分析單個加密貨幣 (使用並行處理 + 數據共享) (已快取)
        """
        # 1. 查找交易所與標準化符號
        if exchange is None:
            result = self.find_available_exchange(symbol)
            if result is None:
                error_msg = f">> 在所有支持的交易所 ({', '.join([e.upper() for e in self.supported_exchanges])}) 都找不到交易對 {symbol}\n"
                # 在生成器模式下，我們拋出異常而不是返回元組
                raise ValueError(error_msg)
            exchange, normalized_symbol = result
        else:
            normalized_symbol = self.normalize_symbol(symbol, exchange)

        print(f">> 準備分析 {normalized_symbol} ({exchange})...")

        try:
            # 2. 🔥 預先抓取數據 (只做一次)
            shared_data = self._fetch_shared_data(normalized_symbol, exchange, interval, limit)
            print(f">> 數據預取完成 (週期: {interval}, 數量: {limit})，正在分發給 AI 分析師...")

            # 3. 定義兩個任務 (注入 preloaded_data)
            spot_state = {
                "symbol": normalized_symbol, "exchange": exchange, "interval": interval,
                "limit": limit, "market_type": 'spot', "leverage": 1,
                "include_multi_timeframe": True,  # 啟用多週期分析
                "short_term_interval": "1h",      # 短週期時間間隔
                "medium_term_interval": "4h",     # 中週期時間間隔
                "long_term_interval": "1d",       # 長週期時間間隔
                "preloaded_data": shared_data # <--- 注入共用數據
            }

            futures_state = {
                "symbol": normalized_symbol, "exchange": exchange, "interval": interval,
                "limit": limit, "market_type": 'futures', "leverage": DEFAULT_FUTURES_LEVERAGE,
                "include_multi_timeframe": True,  # 啟用多週期分析
                "short_term_interval": "1h",      # 短週期時間間隔
                "medium_term_interval": "4h",     # 中週期時間間隔
                "long_term_interval": "1d",       # 長週期時間間隔
                "preloaded_data": shared_data # <--- 注入共用數據
            }

            # 4. 並行執行 AI 分析 (因為數據已經有了，這一步會非常快)
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_ANALYSIS_WORKERS) as executor:
                future_spot = executor.submit(app.invoke, spot_state)
                future_futures = executor.submit(app.invoke, futures_state)

                spot_final_state = future_spot.result()
                futures_final_state = future_futures.result()

            # 5. 返回摘要生成器
            return spot_final_state, futures_final_state, self._generate_summary(spot_final_state, futures_final_state)

        except Exception as e:
            error_msg = f">> 分析 {normalized_symbol} 時發生錯誤: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            # 在生成器模式下，我們拋出異常而不是返回元組
            raise e

    def _generate_summary(self, spot_results: Dict, futures_results: Dict):
        """生成詳細的分析摘要 (改為生成器)"""
        # 使用現貨數據作為主要參考
        primary_results = spot_results or futures_results
        if not primary_results:
            yield ">> 無法生成分析報告，因為沒有收到任何結果。"
            return

        symbol = primary_results.get('symbol', '未知幣種')
        current_price = primary_results.get('current_price', 0)
        exchange = primary_results.get('exchange', 'N/A').upper()

        yield f"## >> {symbol} 深度投資分析報告\n"
        yield f"**交易所**: {exchange}\n"
        yield f"**當前價格**: ${safe_float(current_price):.4f}\n\n" if current_price else "**當前價格**: 無法獲取\n\n"

        # --- 1. 關鍵指標概覽 ---
        summary_parts = ["### >> 關鍵指標概覽"]
        price_info = primary_results.get('價格資訊')
        if price_info:
            change_pct = price_info.get('7天價格變化百分比', 0)
            summary_parts.append(f"- **7天價格變化**: {change_pct:.2f}%")
        
        indicators = primary_results.get('技術指標')
        if indicators:
            rsi = indicators.get('RSI_14', 0)
            summary_parts.append(f"- **RSI (14)**: {rsi:.2f}")

        structure = primary_results.get('市場結構')
        if structure:
            trend = structure.get('趨勢', '未知')
            volatility = structure.get('波動率', 0)
            summary_parts.append(f"- **短期趨勢**: {trend}")
            summary_parts.append(f"- **波動率 (30天)**: {volatility:.2f}%")
        yield "\n".join(summary_parts) + "\n\n"


        # --- 2. 多空觀點辯論 ---
        summary_parts = ["### >> 多空觀點辯論"]
        bull_argument = primary_results.get('bull_argument')
        bear_argument = primary_results.get('bear_argument')
        if bull_argument:
            summary_parts.append(f"** 看多理由 (Bullish):**\n{bull_argument.argument}\n")
        else:
            summary_parts.append(f"** 看多理由 (Bullish):**\n無\n")

        if bear_argument:
            summary_parts.append(f"** 看空理由 (Bearish):**\n{bear_argument.argument}\n")
        else:
            summary_parts.append(f"** 看空理由 (Bearish):**\n無\n")
        yield "\n".join(summary_parts) + "\n"

        # --- 3. 技術分析總結 ---
        tech_report = next((r for r in primary_results.get('analyst_reports', []) if r.analyst_type == '技術分析師'), None)
        if tech_report:
            yield f"### 📉 技術分析\n**分析師觀點**: {tech_report.summary}\n\n"
        else:
            yield "### 📉 技術分析\n無技術分析摘要。\n\n"

        # --- 4. 基本面分析 (新聞) ---
        summary_parts = ["### 📰 新聞與基本面"]
        news_report = next((r for r in primary_results.get('analyst_reports', []) if r.analyst_type == '新聞分析師'), None)
        sentiment_report = next((r for r in primary_results.get('analyst_reports', []) if r.analyst_type == '情緒分析師'), None)
        
        if sentiment_report:
            summary_parts.append(f"**市場情緒**: {sentiment_report.summary}")
        
        if news_report:
            summary_parts.append(f"**新聞摘要**: {news_report.summary}\n")
        else:
            summary_parts.append("無新聞分析摘要。\n")
        yield "\n".join(summary_parts) + "\n"

        # --- 5. 風險評估 ---
        summary_parts = ["### >> 風險評估"]
        if primary_results.get('risk_assessment'):
            risk = primary_results['risk_assessment']
            summary_parts.append(f"- **風險等級**: {risk.risk_level if hasattr(risk, 'risk_level') else '未知'}")
            summary_parts.append(f"- **評估意見**: {risk.assessment if hasattr(risk, 'assessment') else '無'}")
            if hasattr(risk, 'warnings') and risk.warnings:
                summary_parts.append(f"- **潛在風險**: {', '.join(risk.warnings)}")
            else:
                summary_parts.append(f"- **潛在風險**: 無")
            summary_parts.append(f"- **應對建議**: {risk.suggested_adjustments if hasattr(risk, 'suggested_adjustments') else '無'}\n")
        else:
            summary_parts.append("無風險評估詳細資訊。\n")
        yield "\n".join(summary_parts) + "\n"

        # --- 6. 最終交易決策 ---
        yield "### ⚖️ 最終交易決策"

        def format_market_decision(results, market_name):
            if not results:
                return f"\n#### {market_name}\n**決策**: 無數據\n"

            final_approval = results.get('final_approval')
            trader_decision = results.get('trader_decision')

            if not final_approval:
                return f"\n#### {market_name}\n**決策**: 無法獲取最終審批結果\n"

            action_map = {"Buy": ">> 買入", "Sell": ">> 賣出", "Hold": ">> 觀望", "Long": ">> 做多", "Short": ">> 做空"}
            approval_map = {"Approve": ">> 批准", "Amended": ">> 修正後批准", "Reject": ">> 拒絕", "Hold": ">> 觀望"}

            trading_action = trader_decision.decision if trader_decision else 'Hold'
            action_display = action_map.get(trading_action, trading_action)

            approval_status = final_approval.final_decision if hasattr(final_approval, 'final_decision') else "未知"
            approval_display = approval_map.get(approval_status, approval_status)
            
            reasoning = final_approval.rationale if hasattr(final_approval, 'rationale') else "無"

            lines = [f"\n#### {market_name}"]
            lines.append(f"**交易動作**: {action_display}")
            lines.append(f"**審批狀態**: {approval_display}")
            lines.append(f"**審批理由**: {reasoning}")

            if approval_status in ["Approve", "Amended"] and trader_decision:
                lines.append(f"\n**>> 交易計劃**:")
                
                pos_size = final_approval.final_position_size if hasattr(final_approval, 'final_position_size') else 0
                lines.append(f"- **倉位**: {pos_size * 100:.0f}%")
                
                entry = trader_decision.entry_price if hasattr(trader_decision, 'entry_price') else current_price
                if entry is None: entry = current_price
                lines.append(f"- **進場價**: ${safe_float(entry):.4f}")

                stop_loss = trader_decision.stop_loss if hasattr(trader_decision, 'stop_loss') else None
                if stop_loss and entry:
                    loss_pct = abs((safe_float(stop_loss) - safe_float(entry)) / safe_float(entry) * 100)
                    lines.append(f"- **止損**: ${safe_float(stop_loss):.4f} (-{loss_pct:.2f}%)")

                take_profit = trader_decision.take_profit if hasattr(trader_decision, 'take_profit') else None
                if take_profit and entry:
                    profit_pct = abs((safe_float(take_profit) - safe_float(entry)) / safe_float(entry) * 100)
                    lines.append(f"- **止盈**: ${safe_float(take_profit):.4f} (+{profit_pct:.2f}%)")
                
                if "合約" in market_name:  # Check for "futures" in the market name instead of emoji
                    leverage = final_approval.approved_leverage if hasattr(final_approval, 'approved_leverage') else None
                    if leverage:
                        lines.append(f"- **槓桿**: {leverage}x")

            return "\n".join(lines) + "\n"

        if spot_results:
            yield format_market_decision(spot_results, ">> 現貨市場")

        if futures_results:
            yield format_market_decision(futures_results, f">> 合約市場 ({DEFAULT_FUTURES_LEVERAGE}x 槓桿)")

        yield f"\n---\n*分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    def process_message(self, user_message: str, interval: str, limit: int):
        """處理用戶消息 (改為生成器以支持串流, 無狀態)"""
        # 1. 解析用戶意圖
        parsed = self.parser.parse_query(user_message)
        intent = parsed.get("intent", "general_question")
        symbols = parsed.get("symbols", [])
        action = parsed.get("action", "chat")

        response_so_far = ""
        # 2. 根據意圖執行不同操作
        if intent == "greeting":
            response_so_far = "你好！我是加密貨幣投資分析助手，請問有什麼可以為您服務的？"
            yield response_so_far

        elif intent == "investment_analysis" and symbols:
            if action == "compare" and len(symbols) > 1:
                response_so_far = f"好的，我將為您逐一分析比較 {', '.join(symbols)} 的投資價值..."
                yield response_so_far
                for i, symbol in enumerate(symbols):
                    response_so_far += f"\n\n---\n\n### ({i+1}/{len(symbols)}) 正在分析 {symbol}...\n"
                    yield response_so_far
                    try:
                        _, _, summary_generator = self.analyze_crypto(symbol, interval=interval, limit=limit)
                        # 從生成器逐步獲取摘要
                        for part in summary_generator:
                             response_so_far += part
                             yield response_so_far
                    except Exception as e:
                        response_so_far += f"\n>> 分析 {symbol} 時發生錯誤: {e}"
                        yield response_so_far
            else:
                symbol = symbols[0]
                response_so_far = f"好的，正在為您分析 {symbol} 的投資價值...\n"
                yield response_so_far
                try:
                    _, _, summary_generator = self.analyze_crypto(symbol, interval=interval, limit=limit)
                    # 從生成器逐步獲取摘要
                    for part in summary_generator:
                        response_so_far += part
                        yield response_so_far
                except Exception as e:
                    response_so_far += f"\n>> 分析 {symbol} 時發生錯誤: {e}"
                    yield response_so_far
        else:
            response_so_far = "抱歉，我不太理解您的問題。您可以試著問我「比特幣可以投資嗎？」或「比較 ETH 和 SOL」。"
            yield response_so_far


def create_chat_interface():
    """創建 Gradio 聊天界面"""

    bot = CryptoAnalysisBot()

    # 創建界面
    with gr.Blocks(title="加密貨幣投資分析助手") as demo:
        gr.Markdown(
            """
            # 💰 加密貨幣投資分析助手

            歡迎使用智能投資分析系統！我可以幫你分析各種加密貨幣的投資價值。

            **功能特色:**
            - 🤖 自然語言對話，智能識別加密貨幣代號
            - 📊 雙市場分析（現貨 + 合約）
            - 🔍 多維度技術分析
            - ⚖️ 多空辯論與風險評估
            - 📈 專業投資建議

            **使用範例:**
            - "PI 可以投資嗎？"
            - "PIUSDT 值得買入嗎？"
            - "XRP, PI, ETH 哪些可以投資？"
            - "比特幣現在適合進場嗎？"
            """
        )

        chatbot = gr.Chatbot(
            label="對話記錄",
            height=500,
            show_label=True,
            avatar_images=(None, "https://img.icons8.com/fluency/48/000000/robot-3.png") # 添加一個機器人頭像
        )

        with gr.Row():
            msg = gr.Textbox(
                label="輸入你的問題",
                placeholder="例如: PI 可以投資嗎？",
                scale=4
            )
            submit = gr.Button("發送", variant="primary", scale=1)

        with gr.Row():
            interval_dropdown = gr.Dropdown(
                choices=['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d', '1w', '1M'],
                value=DEFAULT_INTERVAL,
                label="⏱️ 時間週期",
                info=f"K線週期（預設: {DEFAULT_INTERVAL}）",
                scale=1
            )
            limit_slider = gr.Slider(
                minimum=50,
                maximum=1000,
                value=DEFAULT_KLINES_LIMIT,
                step=50,
                label="📊 數據量",
                info=f"K線數量（預設: {DEFAULT_KLINES_LIMIT}）",
                scale=2
            )
            clear = gr.Button("清除對話", scale=1)

        gr.Markdown(
            f"""
            ---
            **提示:**
            - 支持的交易所: {', '.join(SUPPORTED_EXCHANGES).upper()}
            - 可自定義時間週期和數據量
            - 合約市場預設使用 {DEFAULT_FUTURES_LEVERAGE}x 槓桿
            - 請謹慎投資，本系統僅供參考
            """
        )

        def respond(message, chat_history, interval, limit):
            """處理用戶消息 (串流模式，已修復格式問題)"""
            if not message.strip():
                yield "", chat_history
                return
            
            # 如果 chat_history 是 None (第一次)，則初始化為空列表
            chat_history = chat_history or []

            # 遵循 [{"role": "user", "content": ...}] 格式
            chat_history.append({"role": "user", "content": message})
            chat_history.append({"role": "assistant", "content": ""})
            yield "", chat_history

            # 逐步更新聊天記錄
            # 注意：process_message 現在是無狀態的，不傳遞 history
            for chunk in bot.process_message(message, interval, limit):
                chat_history[-1]["content"] = chunk
                yield "", chat_history

        # 綁定事件
        msg.submit(respond, [msg, chatbot, interval_dropdown, limit_slider], [msg, chatbot])
        submit.click(respond, [msg, chatbot, interval_dropdown, limit_slider], [msg, chatbot])
        clear.click(lambda: (None, []), None, [msg, chatbot], queue=False)

    return demo

def create_screener_interface():
    """創建加密貨幣篩選器界面"""
    bot = CryptoAnalysisBot()

    with gr.Blocks() as screener_tab:
        gr.Markdown("# 🚀 Top Cryptocurrency Screener")
        with gr.Row():
            exchange_dropdown = gr.Dropdown(choices=SUPPORTED_EXCHANGES, value=SUPPORTED_EXCHANGES[0], label="Exchange")
            run_button = gr.Button("Run Screener", variant="primary")
        
        top_performers_df_state = gr.State(pd.DataFrame())
        
        gr.Markdown(f"### 📈 Top Performers (7-day, Top {SCREENER_DEFAULT_LIMIT})")
        top_performers_df_display = gr.DataFrame(pd.DataFrame(), interactive=False)
        
        with gr.Row():
            debate_button = gr.Button("Debate Top 3", variant="secondary")
        
        debate_results_display = gr.Markdown("")

        gr.Markdown("### 📉 Most Oversold (RSI < 40)")
        oversold_df_display = gr.DataFrame(pd.DataFrame(), interactive=False)
        
        gr.Markdown("### 💹 Most Overbought (RSI > 70)")
        overbought_df_display = gr.DataFrame(pd.DataFrame(), interactive=False)

        def run_screener_and_display(exchange):
            summary_df, top_performers, oversold, overbought = screen_top_cryptos(
                exchange=exchange, 
                limit=SCREENER_DEFAULT_LIMIT, 
                interval=SCREENER_DEFAULT_INTERVAL
            )
            return top_performers, oversold, overbought, top_performers

        def debate_top_performers(top_performers_df, exchange):
            if top_performers_df.empty:
                return "Please run the screener first to identify top performers."

            top_3_symbols = top_performers_df.head(3)['Symbol'].tolist()
            
            all_summaries = []
            for symbol in top_3_symbols:
                try:
                    # analyze_crypto 現在返回一個生成器作為第三個元素
                    _, _, summary_generator = bot.analyze_crypto(symbol, exchange=exchange)
                    # 將生成器的所有部分組合成一個完整的字符串
                    full_summary = "".join(list(summary_generator))
                    all_summaries.append(full_summary)
                except Exception as e:
                    all_summaries.append(f"### {symbol}\n>> 分析時發生錯誤: {e}")

            return "\n\n---\n\n".join(all_summaries)

        run_button.click(
            run_screener_and_display,
            inputs=[exchange_dropdown],
            outputs=[top_performers_df_display, oversold_df_display, overbought_df_display, top_performers_df_state]
        )
        
        debate_button.click(
            debate_top_performers,
            inputs=[top_performers_df_state, exchange_dropdown],
            outputs=[debate_results_display]
        )

    return screener_tab


if __name__ == "__main__":
    # 啟動帶有選項卡的界面
    demo = gr.TabbedInterface(
        [create_chat_interface(), create_screener_interface()],
        ["Chat with Agent", "Crypto Screener"]
    )
    demo.launch(
        server_name="0.0.0.0",
        server_port=7868,
        share=False,
        show_error=True
    )