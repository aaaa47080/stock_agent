"""
聊天界面模組 - 使用 Gradio 創建對話式加密貨幣投資分析界面
支持自然語言查詢，智能提取加密貨幣代號並進行分析
"""

import gradio as gr
import os
import re
from typing import List, Dict, Tuple, Optional
import openai
from dotenv import load_dotenv
from graph import app
from data_fetcher import SymbolNotFoundError, get_data_fetcher
import json
from datetime import datetime
from data_fetcher import get_data_fetcher
from utils import get_crypto_news
from indicator_calculator import add_technical_indicators
import concurrent.futures  # <--- 記得加在文件最上面
from crypto_screener import screen_top_cryptos
import pandas as pd

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
                model="gpt-4o",
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
        self.chat_history = []
        # 支持的交易所列表，按優先級排序
        self.supported_exchanges = ["binance", "okx"]

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

    def find_available_exchange(self, symbol: str) -> Optional[Tuple[str, str]]:
        """查找交易對可用的交易所"""
        for exchange in self.supported_exchanges:
            try:
                normalized = self.normalize_symbol(symbol, exchange)
                fetcher = get_data_fetcher(exchange)
                test_data = fetcher.get_historical_klines(normalized, "1d", limit=1)
                if test_data is not None and not test_data.empty:
                    print(f"✅ 在 {exchange.upper()} 找到交易對: {normalized}")
                    return (exchange, normalized)
            except:
                continue
        return None

    def _fetch_shared_data(self, symbol: str, exchange: str, interval: str = "1d", limit: int = 100) -> Dict:
        """
        🔥 核心功能：手動預先抓取數據 (只抓一次，供兩邊使用)
        這段邏輯是從 graph.py 的 prepare_data_node 提取出來的
        """
        print(f"📥 正在預先下載共用數據: {symbol}...")
        
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
        current_price = float(latest['Close'])
        
        # 最近5天歷史
        recent_history = []
        recent_days = min(5, len(df_with_indicators))
        for i in range(-recent_days, 0):
            day_data = df_with_indicators.iloc[i]
            recent_history.append({
                "日期": i, "開盤": float(day_data['Open']), "最高": float(day_data['High']),
                "最低": float(day_data['Low']), "收盤": float(day_data['Close']), "交易量": float(day_data['Volume'])
            })

        # 關鍵價位
        recent_30 = df_with_indicators.tail(30) if len(df_with_indicators) >= 30 else df_with_indicators
        key_levels = {
            "30天最高價": float(recent_30['High'].max()), "30天最低價": float(recent_30['Low'].min()),
            "支撐位": float(recent_30['Low'].quantile(0.25)), "壓力位": float(recent_30['High'].quantile(0.75)),
        }

        # 市場結構
        price_changes = df_with_indicators['Close'].pct_change()
        market_structure = {
            "趨勢": "上漲" if price_changes.tail(7).mean() > 0 else "下跌",
            "波動率": float(price_changes.tail(30).std() * 100) if len(price_changes) >= 30 else 0,
            "平均交易量": float(df_with_indicators['Volume'].tail(7).mean()),
        }

        # 返回共用數據包
        return {
            "market_type": "spot", # 這裡先標記為 spot，傳入 graph 後會被覆蓋
            "exchange": exchange,
            "leverage": 1,
            "funding_rate_info": {}, # 共用數據暫不包含合約特定的資金費率
            "價格資訊": {
                "當前價格": current_price,
                "7天價格變化百分比": float(((latest['Close'] / df_with_indicators.iloc[-7]['Close']) - 1) * 100) if len(df_with_indicators) >= 7 else 0,
            },
            "技術指標": {
                "RSI_14": float(latest.get('RSI_14', 0)), "MACD_線": float(latest.get('MACD_12_26_9', 0)),
                "布林帶上軌": float(latest.get('BB_upper_20_2', 0)), "布林帶下軌": float(latest.get('BB_lower_20_2', 0)),
                "MA_7": float(latest.get('MA_7', 0)), "MA_25": float(latest.get('MA_25', 0)),
            },
            "最近5天歷史": recent_history,
            "市場結構": market_structure,
            "關鍵價位": key_levels,
            "新聞資訊": news_data
        }

    def analyze_crypto(self, symbol: str, exchange: str = None, interval: str = "1d", limit: int = 100) -> Tuple[Optional[Dict], Optional[Dict], str]:
        """
        分析單個加密貨幣 (使用並行處理 + 數據共享)
        """
        # 1. 查找交易所與標準化符號
        if exchange is None:
            result = self.find_available_exchange(symbol)
            if result is None:
                error_msg = f"❌ 在所有支持的交易所 ({', '.join([e.upper() for e in self.supported_exchanges])}) 都找不到交易對 {symbol}\n"
                return None, None, error_msg
            exchange, normalized_symbol = result
        else:
            normalized_symbol = self.normalize_symbol(symbol, exchange)

        print(f"🚀 準備分析 {normalized_symbol} ({exchange})...")

        try:
            # 2. 🔥 預先抓取數據 (只做一次)
            shared_data = self._fetch_shared_data(normalized_symbol, exchange, interval, limit)
            print(f"✅ 數據預取完成 (週期: {interval}, 數量: {limit})，正在分發給 AI 分析師...")

            # 3. 定義兩個任務 (注入 preloaded_data)
            spot_state = {
                "symbol": normalized_symbol, "exchange": exchange, "interval": interval,
                "limit": limit, "market_type": 'spot', "leverage": 1,
                "preloaded_data": shared_data # <--- 注入共用數據
            }

            futures_state = {
                "symbol": normalized_symbol, "exchange": exchange, "interval": interval,
                "limit": limit, "market_type": 'futures', "leverage": 5,
                "preloaded_data": shared_data # <--- 注入共用數據
            }

            # 4. 並行執行 AI 分析 (因為數據已經有了，這一步會非常快)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_spot = executor.submit(app.invoke, spot_state)
                future_futures = executor.submit(app.invoke, futures_state)

                spot_final_state = future_spot.result()
                futures_final_state = future_futures.result()

            # 5. 生成摘要
            summary = self._generate_summary(spot_final_state, futures_final_state)
            return spot_final_state, futures_final_state, summary

        except Exception as e:
            error_msg = f"❌ 分析 {normalized_symbol} 時發生錯誤: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return None, None, error_msg

    def _generate_summary(self, spot_results: Dict, futures_results: Dict) -> str:
        """生成分析摘要 (修復版)"""
        summary_parts = []
        symbol = spot_results.get('symbol', '未知幣種')
        current_price = spot_results.get('current_price', 0)
        exchange = spot_results.get('exchange', 'N/A').upper()

        summary_parts.append(f"## 📊 {symbol} 投資分析報告\n")
        summary_parts.append(f"**交易所**: {exchange}")
        summary_parts.append(f"**當前價格**: ${float(current_price):.4f}\n" if current_price else "**當前價格**: 無法獲取\n")

        def get_decision_data(approval_obj):
            if not approval_obj: return "未知", "無數據"
            decision = getattr(approval_obj, 'final_decision', getattr(approval_obj, 'decision', 'Hold'))
            reasoning = "無法讀取詳細理由"
            for field in ['reasoning', 'analysis', 'explanation', 'rationale', 'content']:
                if hasattr(approval_obj, field) and getattr(approval_obj, field):
                    reasoning = str(getattr(approval_obj, field))
                    break
            if len(reasoning) > 300: reasoning = reasoning[:300] + "..."
            return decision, reasoning

        def format_market_info(results, market_name):
            """格式化單個市場的信息，包含價格"""
            if not results.get('final_approval'):
                return f"\n### {market_name}\n**決策**: 無數據\n"

            decision, reasoning = get_decision_data(results['final_approval'])
            trader_decision = results.get('trader_decision')
            approval = results['final_approval']

            # 獲取實際的交易動作
            trading_action = trader_decision.decision if trader_decision else "Hold"

            # 交易動作映射（轉換為中文）
            action_map = {
                "Buy": "🟢 買入",
                "Sell": "🔴 賣出",
                "Hold": "⏸️ 觀望",
                "Long": "🟢 做多",
                "Short": "🔴 做空"
            }
            action_display = action_map.get(trading_action, trading_action)

            # 審批結果
            approval_map = {
                "Approve": "✅ 批准",
                "Amended": "⚠️ 修正後批准",
                "Reject": "❌ 拒絕",
                "Hold": "⏸️ 觀望"
            }
            approval_display = approval_map.get(decision, decision)

            lines = [f"\n### {market_name}"]
            lines.append(f"**交易動作**: {action_display}")
            lines.append(f"**審批狀態**: {approval_display}")
            lines.append(f"**理由**: {reasoning}")

            # 如果批准交易，顯示價格信息
            if approval.approved and approval.final_position_size > 0 and trader_decision:
                lines.append(f"\n**📊 交易計劃**:")
                lines.append(f"- **倉位**: {approval.final_position_size * 100:.0f}%")

                if trader_decision.entry_price:
                    lines.append(f"- **進場價**: ${trader_decision.entry_price:.4f}")
                else:
                    lines.append(f"- **進場價**: 市價 (${current_price:.4f})")

                if trader_decision.stop_loss:
                    loss_pct = abs((trader_decision.stop_loss - current_price) / current_price * 100)
                    lines.append(f"- **止損**: ${trader_decision.stop_loss:.4f} (-{loss_pct:.2f}%)")

                if trader_decision.take_profit:
                    profit_pct = abs((trader_decision.take_profit - current_price) / current_price * 100)
                    lines.append(f"- **止盈**: ${trader_decision.take_profit:.4f} (+{profit_pct:.2f}%)")

                # 如果是合約，顯示槓桿
                if approval.approved_leverage:
                    lines.append(f"- **槓桿**: {approval.approved_leverage}x")

            return "\n".join(lines) + "\n"

        if 'final_approval' in spot_results and spot_results['final_approval']:
            summary_parts.append(format_market_info(spot_results, "🏪 現貨市場"))

        if 'final_approval' in futures_results and futures_results['final_approval']:
            summary_parts.append(format_market_info(futures_results, "📈 合約市場 (5x 槓桿)"))

        if 'risk_assessment' in spot_results and spot_results['risk_assessment']:
            risk_obj = spot_results['risk_assessment']
            risk_level = getattr(risk_obj, 'risk_level', getattr(risk_obj, 'level', '未知'))
            summary_parts.append(f"\n**風險等級**: {risk_level}")

        summary_parts.append(f"\n---\n*分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        return "\n".join(summary_parts)
    
    def process_message(self, user_message: str, history: List, interval: str = "1d", limit: int = 100) -> Tuple[str, List]:
        # (這裡保持你不變的原始代碼， क्योंकि इसमें कोई बदलाव नहीं है)
        if not user_message.strip():
            return "", history
        parsed = self.parser.parse_query(user_message)
        intent = parsed.get("intent", "general_question")
        symbols = parsed.get("symbols", [])
        action = parsed.get("action", "chat")

        if intent == "greeting":
            response = "你好！我是加密貨幣投資分析助手..."
        elif intent == "investment_analysis" and symbols:
            if action == "compare" and len(symbols) > 1:
                response = f"我來為你分析比較 {', '.join(symbols)} 的投資價值...\n\n"
                all_summaries = []
                for symbol in symbols:
                    spot_results, futures_results, summary = self.analyze_crypto(symbol, interval=interval, limit=limit)
                    if spot_results or futures_results:
                        all_summaries.append(summary)
                    else:
                        all_summaries.append(f"### {symbol}\n{summary}")
                response += "\n\n".join(all_summaries)
            else:
                symbol = symbols[0]
                response = f"正在為你分析 {symbol} 的投資價值...\n\n"
                spot_results, futures_results, summary = self.analyze_crypto(symbol, interval=interval, limit=limit)
                response += summary
        else:
            response = "抱歉，我沒有理解你的問題..."

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response})
        return "", history


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
            show_label=True
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
                value='1d',
                label="⏱️ 時間週期",
                info="K線週期（預設: 1天）",
                scale=1
            )
            limit_slider = gr.Slider(
                minimum=50,
                maximum=1000,
                value=100,
                step=50,
                label="📊 數據量",
                info="K線數量（預設: 100）",
                scale=2
            )
            clear = gr.Button("清除對話", scale=1)

        gr.Markdown(
            """
            ---
            **提示:**
            - 支持的交易所: Binance (預設), OKX
            - 可自定義時間週期和數據量
            - 合約市場預設使用 5x 槓桿
            - 請謹慎投資，本系統僅供參考
            """
        )

        def respond(message, chat_history, interval, limit):
            """處理用戶消息"""
            response, updated_history = bot.process_message(message, chat_history, interval, limit)
            return "", updated_history

        # 綁定事件
        msg.submit(respond, [msg, chatbot, interval_dropdown, limit_slider], [msg, chatbot])
        submit.click(respond, [msg, chatbot, interval_dropdown, limit_slider], [msg, chatbot])
        clear.click(lambda: None, None, chatbot, queue=False)

    return demo

def create_screener_interface():
    """創建加密貨幣篩選器界面"""
    bot = CryptoAnalysisBot()

    with gr.Blocks() as screener_tab:
        gr.Markdown("# 🚀 Top 30 Cryptocurrency Screener")
        with gr.Row():
            exchange_dropdown = gr.Dropdown(choices=["binance", "okx"], value="binance", label="Exchange")
            run_button = gr.Button("Run Screener", variant="primary")
        
        top_performers_df_state = gr.State(pd.DataFrame())
        
        gr.Markdown("### 📈 Top Performers (7-day)")
        top_performers_df_display = gr.DataFrame(pd.DataFrame(), interactive=False)
        
        with gr.Row():
            debate_button = gr.Button("Debate Top 3", variant="secondary")
        
        debate_results_display = gr.Markdown("")

        gr.Markdown("### 📉 Most Oversold (RSI < 40)")
        oversold_df_display = gr.DataFrame(pd.DataFrame(), interactive=False)
        
        gr.Markdown("### 💹 Most Overbought (RSI > 70)")
        overbought_df_display = gr.DataFrame(pd.DataFrame(), interactive=False)

        def run_screener_and_display(exchange):
            summary_df, top_performers, oversold, overbought = screen_top_cryptos(exchange=exchange, limit=30, interval='1d')
            return top_performers, oversold, overbought, top_performers

        def debate_top_performers(top_performers_df, exchange):
            if top_performers_df.empty:
                return "Please run the screener first to identify top performers."

            top_3_symbols = top_performers_df.head(3)['Symbol'].tolist()
            
            all_summaries = []
            for symbol in top_3_symbols:
                _, _, summary = bot.analyze_crypto(symbol, exchange=exchange)
                all_summaries.append(summary)
            
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