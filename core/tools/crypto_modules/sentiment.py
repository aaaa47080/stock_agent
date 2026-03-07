"""
市場情緒工具
Fear & Greed Index, Trending Tokens, Futures Data, Current Time
"""
import time
from typing import Dict
from langchain_core.tools import tool
import httpx

from .common import get_cached_data, set_cached_data


_COINGECKO_CACHE: Dict = {}


def _get_cached_coingecko_data(key: str, ttl_seconds: int = 300):
    if key in _COINGECKO_CACHE:
        timestamp, data = _COINGECKO_CACHE[key]
        if time.time() - timestamp < ttl_seconds:
            return data
    return None


def _set_cached_coingecko_data(key: str, data):
    _COINGECKO_CACHE[key] = (time.time(), data)


@tool
def get_fear_and_greed_index() -> str:
    """獲取加密貨幣市場全域的恐慌與貪婪指數 (Fear and Greed Index)"""
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


@tool
def get_trending_tokens() -> str:
    """獲取目前全網最熱門搜尋的加密貨幣 (Trending Tokens)"""
    cache_key = "trending_tokens"
    cached_data = _get_cached_coingecko_data(cache_key, 300)
    if cached_data:
        return cached_data

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
        return "目前無法連線到 CoinGecko API。"
    except Exception as e:
        return f"取得熱門搜尋幣種時發生網路錯誤: {str(e)}"


@tool
def get_futures_data(symbol: str) -> str:
    """獲取加密貨幣永續合約的資金費率 (Funding Rate)"""
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
        return f"找不到 {symbol} 的合約數據。"
    except Exception as e:
        return f"取得資金費率時發生網路錯誤: {str(e)}"


@tool
def get_current_time_taipei() -> str:
    """獲取目前台灣/UTC+8的精準時間與日期"""
    from datetime import datetime
    import pytz

    tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(tz)

    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M:%S")
    weekday_str = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]

    return f"🕰️ 【當前系統時間 (UTC+8)】\n日期：{date_str} ({weekday_str})\n時間：{time_str}"
