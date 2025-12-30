import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
import pandas as pd
from openai import OpenAI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.utils import get_crypto_news, safe_float
from data.market_data import get_klines
from core.config import FAST_THINKING_MODEL

# Configure logging
logger = logging.getLogger(__name__)

class MarketPulseAnalyzer:
    """
    Market Pulse Analyzer: Explains WHY the market is moving.
    Combines price volatility detection with news correlation.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def analyze_movement(self, symbol: str, threshold_percent: float = 2.0, enabled_sources: List[str] = None) -> Dict:
        """
        Analyze recent market movement and provide a narrative explanation.
        
        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'ETH')
            threshold_percent: Minimum percentage change to trigger deep analysis
            enabled_sources: List of news source IDs to fetch from
            
        Returns:
            Dict containing volatility data, news, and the AI-generated explanation.
        """
        # 1. Get recent price data (1h timeframe, last 24 candles)
        # We need enough data to calculate 24h change and see recent spikes
        df = get_klines(symbol, interval="1h", limit=24)
        
        if df is None or df.empty:
            return {"error": f"無法獲取 {symbol} 的價格數據"}
            
        current_price = safe_float(df.iloc[-1]['close'])
        open_price_1h = safe_float(df.iloc[-1]['open'])
        price_24h_ago = safe_float(df.iloc[0]['open'])
        
        # Calculate changes
        change_1h = ((current_price - open_price_1h) / open_price_1h) * 100
        change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
        
        is_volatile = abs(change_1h) >= threshold_percent or abs(change_24h) >= 5.0
        
        result = {
            "symbol": symbol,
            "current_price": current_price,
            "change_1h": change_1h,
            "change_24h": change_24h,
            "is_volatile": is_volatile,
            "timestamp": datetime.now().isoformat(),
            "explanation": None,
            "news_sources": []
        }
        
        # 2. If volatile or requested, fetch news and explain
        # We always fetch news to provide context, but the prompt changes based on volatility
        news_limit = 5
        news_data = get_crypto_news(symbol, limit=news_limit, enabled_sources=enabled_sources)
        result["news_sources"] = news_data
        
        # 3. Generate Narrative using LLM
        narrative = self._generate_narrative(symbol, change_1h, change_24h, news_data)
        result["explanation"] = narrative
        
        return result

    def _generate_narrative(self, symbol: str, change_1h: float, change_24h: float, news_data: List[Dict]) -> str:
        """
        Uses LLM to synthesize price movement with news.
        """
        
        trend_1h = "上漲" if change_1h > 0 else "下跌"
        trend_24h = "上漲" if change_24h > 0 else "下跌"
        
        # Format news for the prompt
        news_context = "近期沒有相關新聞。"
        if news_data:
            news_items = []
            for n in news_data[:5]:
                title = n.get('title', 'N/A')
                desc = n.get('description', '')
                source = n.get('source', 'Unknown')
                news_items.append(f"- [{source}] {title}: {desc}")
            news_context = "\n".join(news_items)
            
        prompt = f"""
你是一位專業的加密貨幣市場分析師。請根據以下數據，用**一句簡短、自然的人話**解釋 {symbol} 的行情波動原因。

**市場數據**:
- 1小時走勢: {trend_1h} {abs(change_1h):.2f}%
- 24小時走勢: {trend_24h} {abs(change_24h):.2f}%

**近期新聞**:
{news_context}

**任務**:
1. 如果有相關新聞能解釋波動，請直接關聯（例如：「受到 SEC 延後 ETF 決議的影響，BTC 短線下跌 3%...」）。
2. 如果沒有明確新聞，請基於市場情緒或技術面做一般性解釋（例如：「BTC 在缺乏重大利好消息下，跟隨大盤小幅回調...」）。
3. **語氣要像老練的交易員**，不要像機器人。
4. **長度限制**: 50 字以內。

請直接輸出解釋內容，不要加引號或其他廢話。
"""
        try:
            response = self.client.chat.completions.create(
                model=FAST_THINKING_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            return f"{symbol} 短線波動 {change_1h:.2f}%，目前市場情緒{trend_1h}。"

# Global instance
market_pulse = MarketPulseAnalyzer()

def get_market_pulse(symbol: str, enabled_sources: List[str] = None) -> Dict:
    """Wrapper function to be used by API/Tools"""
    return market_pulse.analyze_movement(symbol, enabled_sources=enabled_sources)

if __name__ == "__main__":
    # Test
    print(json.dumps(get_market_pulse("BTC"), indent=2, ensure_ascii=False))
