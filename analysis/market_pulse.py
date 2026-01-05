import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.utils import get_crypto_news, safe_float, DataFrameEncoder
from data.market_data import get_klines
from data.indicator_calculator import add_technical_indicators
from core.config import MARKET_PULSE_MODEL
from utils.llm_client import create_llm_client_from_config

# Configure logging
logger = logging.getLogger(__name__)

class MarketPulseAnalyzer:
    """
    Market Pulse Analyzer: Explains WHY the market is moving.
    Combines price volatility detection with news correlation and technicals.
    ⭐ 使用用戶提供的 LLM client
    """

    def __init__(self, client=None):
        """
        初始化 MarketPulseAnalyzer

        Args:
            client: LLM 客戶端（用戶提供）。如果未提供，則嘗試從配置創建。
        """
        if client is None:
            try:
                self.client, self.model = create_llm_client_from_config(MARKET_PULSE_MODEL)
                logger.info("MarketPulseAnalyzer initialized with system config")
            except Exception as e:
                logger.warning(f"MarketPulseAnalyzer initialized WITHOUT LLM (Fallback Mode): {e}")
                self.client = None
                self.model = None
        else:
            self.client = client
            self.model = "user-provided-model"
            logger.info("MarketPulseAnalyzer initialized with user client")
        
    def analyze_movement(self, symbol: str, threshold_percent: float = 2.0, enabled_sources: List[str] = None, skip_llm: bool = False) -> Dict:
        """
        Analyze recent market movement.
        
        Args:
            symbol: Crypto symbol
            threshold_percent: Volatility threshold
            enabled_sources: News sources
            skip_llm: If True, skips LLM generation even if client is available (for fast fallback)
        """
        # 1. Get recent price data
        df = get_klines(symbol, interval="1h", limit=100)
        
        if df is None or df.empty:
            return {"error": f"無法獲取 {symbol} 的價格數據"}
        
        # ... (Technical Analysis code remains same) ...
        # 2. Calculate Technical Indicators
        try:
            df = df.rename(columns={
                'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
            })
            df = add_technical_indicators(df)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            current_price = safe_float(latest['Close'])
            rsi_14 = safe_float(latest.get('RSI_14', 0))
            macd_hist = safe_float(latest.get('MACDh_12_26_9', 0))
            prev_macd_hist = safe_float(prev.get('MACDh_12_26_9', 0))
            
            bb_upper = safe_float(latest.get('BBU_20_2.0', 0))
            bb_lower = safe_float(latest.get('BBL_20_2.0', 0))
            
            vol_sma_20 = df['Volume'].rolling(window=20).mean().iloc[-1]
            current_vol = safe_float(latest['Volume'])
            vol_ratio = current_vol / vol_sma_20 if vol_sma_20 > 0 else 1.0
            vol_status = f"放量 ({vol_ratio:.1f}x)" if vol_ratio > 1.5 else ("縮量" if vol_ratio < 0.7 else "正常")

            macd_trend = "增強" if macd_hist > prev_macd_hist else "減弱"
            macd_signal = "黃金交叉" if macd_hist > 0 and prev_macd_hist <= 0 else ("死亡交叉" if macd_hist < 0 and prev_macd_hist >= 0 else "延續")
            
            technicals = {
                "RSI": rsi_14,
                "MACD_Hist": macd_hist,
                "MACD_Trend": macd_trend,
                "MACD_Signal": macd_signal,
                "BB_Position": (current_price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5,
                "Volume_Status": vol_status,
                "Volume_Ratio": vol_ratio
            }
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            technicals = {}
            current_price = safe_float(df.iloc[-1]['Close'])

        # Calculate changes
        if len(df) >= 25:
            price_1h_ago = safe_float(df.iloc[-2]['Close']) 
            price_24h_ago = safe_float(df.iloc[-25]['Close'])
            change_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100
            change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
        else:
            change_1h = 0.0
            change_24h = 0.0
        
        is_volatile = abs(change_1h) >= threshold_percent or abs(change_24h) >= 5.0
        
        # 3. Fetch News
        news_limit = 8
        news_data = get_crypto_news(symbol, limit=news_limit, enabled_sources=enabled_sources)
        
        # 4. Generate Report
        # Only use LLM if client exists AND skip_llm is False
        if self.client and not skip_llm:
            report = self._generate_structured_report(symbol, current_price, change_1h, change_24h, technicals, news_data)
        else:
            # Fallback Report (Fast Rule-based)
            trend_str = "上漲" if change_24h > 0 else "下跌"
            rsi_status = "超買" if technicals.get('RSI', 50) > 70 else "超賣" if technicals.get('RSI', 50) < 30 else "中性"
            
            # Determine reason for fallback
            if self.client:
                reason = "AI 分析正在後台排隊中，稍後刷新即可查看完整報告。"
                risk_msg = "此為即時數據快照，AI 深度分析運算中..."
            else:
                reason = "如需完整 AI 深度分析，請點擊下方的「深度」按鈕並配置您的 API Key。"
                risk_msg = "未配置 AI 金鑰，僅顯示基礎數據。"
            
            report = {
                "summary": f"**[快速預覽]** {symbol} 現價 ${current_price:,.2f}，24小時{trend_str} {abs(change_24h):.2f}%。技術指標顯示 RSI 為 {rsi_status} ({technicals.get('RSI',0):.1f})。\n\n> {reason}",
                "key_points": [
                    f"**價格走勢**: 1H {change_1h:+.2f}%, 24H {change_24h:+.2f}%",
                    f"**技術信號**: MACD {technicals.get('MACD_Trend', 'N/A')}, 成交量 {technicals.get('Volume_Status', 'N/A')}",
                    f"**新聞動態**: 檢索到 {len(news_data)} 條相關新聞"
                ],
                "highlights": [
                    {"title": "技術面概覽", "content": f"RSI: {technicals.get('RSI',0):.1f}, MACD: {technicals.get('MACD_Signal','N/A')}"}
                ],
                "risks": [risk_msg]
            }
            if news_data:
                top_news = news_data[0]
                report["highlights"].append({
                    "title": "最新消息",
                    "content": f"[{top_news.get('source')}] {top_news.get('title')}"
                })

        result = {
            "symbol": symbol,
            "current_price": current_price,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "is_volatile": is_volatile,
            "timestamp": datetime.now().isoformat(),
            "explanation": report.get("summary", ""),
            "report": report,
            "news_sources": news_data
        }
        
        return result

    def _generate_structured_report(self, symbol: str, price: float, change_1h: float, change_24h: float, technicals: Dict, news_data: List[Dict]) -> Dict:
        """
        Uses LLM to generate a Binance-style structured report.
        """
        
        trend_24h = "上漲" if change_24h > 0 else "下跌"
        
        # Format news
        news_context = "近期沒有相關新聞。"
        if news_data:
            news_items = []
            for n in news_data:
                title = n.get('title', 'N/A')
                desc = n.get('description', '')
                source = n.get('source', 'Unknown')
                news_items.append(f"- [{source}] {title}: {desc}")
            news_context = "\n".join(news_items)

        # Technical context
        tech_context = "數據不足"
        if technicals:
            tech_context = (
                f"RSI(14): {technicals.get('RSI', 0):.1f} ({'超買' if technicals.get('RSI',0)>70 else '超賣' if technicals.get('RSI',0)<30 else '中性'})\n"
                f"MACD柱狀圖: {technicals.get('MACD_Hist', 0):.4f} (動能{technicals.get('MACD_Trend', '')}, {technicals.get('MACD_Signal', '')})\n"
                f"布林帶位置: {technicals.get('BB_Position', 0.5):.2f} (0=下軌, 1=上軌)\n"
                f"成交量狀態: {technicals.get('Volume_Status', 'N/A')}"
            )

        prompt = f"""
你是一位頂級的加密貨幣研究員（類似 Binance Research 風格）。請根據以下數據，為 {symbol} 撰寫一份結構化的「市場脈動」快報。

**市場數據**:
- 當前價格: ${price:,.2f}
- 24小時走勢: {trend_24h} {abs(change_24h):.2f}%
- 1小時走勢: {change_1h:+.2f}%

**技術指標 (1H)**:
{tech_context}

**近期新聞**:
{news_context}

**任務要求**:
請生成一個 JSON 對象，包含以下欄位：
1. **summary** (String): 一句簡短的總結，包含價格動向與主要驅動因素（例如：「比特幣在過去 24 小時內上漲 1.08%，達到 88,255 美元，顯示出溫和的上升動能。」）。
2. **key_points** (List[String]): 3 個核心要點，請使用「**標題**: 內容」的格式。
   - 範例：
     - "**機構信心**: Metaplanet 大量購入比特幣，凸顯機構持續看好..."
     - "**巨鯨佈局**: 鏈上數據顯示..."
     - "**市場脆弱性**: 槓桿水平過高..."
3. **highlights** (List[Dict]): 3-4 個詳細亮點。每個亮點需包含 `title` (標題) 和 `content` (內容)。
   - **必須嘗試提取具體數字**（如金額、數量、日期），如果新聞中有提到的話。
   - 其中一點必須是關於**技術面**（引用上面的 MACD/RSI/成交量 數據）。
   - 如果有機構或巨鯨新聞，請單獨列為一點。
4. **risks** (List[String]): 2-3 個潛在風險提示（例如：槓桿過高、現貨需求疲弱、RSI 背離、宏觀經濟不確定性等）。

**注意**:
- 使用繁體中文。
- 語氣專業、客觀、數據導向。
- 如果新聞沒有具體細節，請根據市場數據進行合理推論，但不要編造假數字。
- 如果新聞為空，請更多地依賴技術指標進行分析。

請直接輸出 JSON，不要加 markdown 標記。
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            # Clean markdown code blocks if present
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            # Fallback structure
            return {
                "summary": f"{symbol} 目前價格 ${price:,.2f}，24小時{trend_24h} {abs(change_24h):.2f}%。",
                "key_points": ["市場波動持續", "需關注後續成交量變化", "技術指標顯示震盪"],
                "highlights": [
                    {"title": "價格表現", "content": f"過去24小時變動 {change_24h:.2f}%，目前處於盤整階段。"},
                    {"title": "技術面", "content": tech_context}
                ],
                "risks": ["市場情緒不明朗", "短線波動風險"]
            }

# Global instance (Lazy Loading)
_market_pulse = None

def get_market_pulse(symbol: str, enabled_sources: List[str] = None) -> Dict:
    """
    Wrapper function to be used by API/Tools

    ✅ 使用懶加載模式：只在實際調用時才創建 MarketPulseAnalyzer 實例
    這樣即使沒有 LLM API Key，服務器也能正常啟動
    """
    global _market_pulse

    if _market_pulse is None:
        # 第一次調用時才創建實例
        try:
            _market_pulse = MarketPulseAnalyzer()
            logger.info("✅ MarketPulseAnalyzer 實例已創建（懶加載）")
        except Exception as e:
            logger.error(f"❌ 創建 MarketPulseAnalyzer 失敗: {e}")
            # 返回錯誤信息，而不是讓整個應用崩潰
            return {
                "error": "LLM_NOT_CONFIGURED",
                "message": "請先在設置中配置 LLM API Key",
                "details": str(e)
            }

    return _market_pulse.analyze_movement(symbol, enabled_sources=enabled_sources)

if __name__ == "__main__":
    # Test
    print(json.dumps(get_market_pulse("BTC"), indent=2, ensure_ascii=False, cls=DataFrameEncoder))
