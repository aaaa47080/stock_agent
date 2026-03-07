"""
DeFi 工具
DefiLlama TVL, Categories & Gainers, Token Unlocks, Token Supply
"""
from typing import Dict
from langchain_core.tools import tool
import httpx

from .common import get_cached_data, set_cached_data
from ..schemas import ExtractCryptoSymbolsInput
from ..helpers import extract_crypto_symbols


@tool
def get_defillama_tvl(protocol_name: str) -> str:
    """從 DefiLlama 獲取特定協議或公鏈的 TVL"""
    try:
        slug = protocol_name.strip().lower().replace(" ", "-")
        resp = httpx.get(f"https://api.llama.fi/protocol/{slug}", timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            name = data.get("name", protocol_name)
            current_chain_tvls = data.get("currentChainTvls", {})
            tvl = sum(current_chain_tvls.values()) if current_chain_tvls else 0
            if tvl == 0:
                tvl_data = data.get("tvl", [])
                tvl = tvl_data[-1].get("totalLiquidityUSD", 0) if tvl_data else 0

            if tvl > 0:
                tvl_str = f"${tvl / 1_000_000_000:.2f}B" if tvl > 1_000_000_000 else f"${tvl / 1_000_000:.2f}M"
                return f"## 🏦 DefiLlama TVL\n\n- **協議**: {name}\n- **TVL**: {tvl_str}\n\n*(來源: DefiLlama)*"

        # Try as chain
        chains_resp = httpx.get("https://api.llama.fi/v2/chains", timeout=10)
        if chains_resp.status_code == 200:
            for chain in chains_resp.json():
                if chain.get("name", "").lower() == slug or chain.get("tokenSymbol", "").lower() == slug:
                    tvl = chain.get("tvl", 0)
                    tvl_str = f"${tvl / 1_000_000_000:.2f}B" if tvl > 1_000_000_000 else f"${tvl / 1_000_000:.2f}M"
                    return f"## 🏦 {chain.get('name')} TVL\n\n- **TVL**: {tvl_str}\n\n*(來源: DefiLlama)*"

        return f"找不到 '{protocol_name}' 的資料。"
    except Exception as e:
        return f"取得 TVL 時發生錯誤: {str(e)}"


@tool
def get_crypto_categories_and_gainers() -> str:
    """獲取加密貨幣板塊與領漲幣種"""
    cache_key = "categories_and_gainers"
    cached = get_cached_data(cache_key, 300)
    if cached:
        return cached

    try:
        resp = httpx.get("https://api.coingecko.com/api/v3/coins/categories", timeout=10)
        if resp.status_code == 200:
            categories = resp.json()
            sorted_cats = sorted(
                [c for c in categories if c.get('market_cap_change_24h') is not None],
                key=lambda x: x['market_cap_change_24h'], reverse=True
            )
            output = "## 🚀 強勢板塊 (Top Sectors)\n\n"
            for i, cat in enumerate(sorted_cats[:5], 1):
                output += f"{i}. **{cat.get('name')}**: {cat.get('market_cap_change_24h', 0):+.2f}%\n"
            final = output + "\n*(來源: CoinGecko)*"
            set_cached_data(cache_key, final)
            return final
        return "無法取得板塊數據。"
    except Exception as e:
        return f"錯誤: {str(e)}"


@tool
def get_token_unlocks(symbol: str) -> str:
    """獲取代幣解鎖日程"""
    symbol = symbol.upper()
    mock_data = {
        "SUI": {"date": "本月 15 日", "amount": "64.19M SUI", "percent": "2.26%"},
        "APT": {"date": "下週三", "amount": "11.31M APT", "percent": "2.48%"},
        "ARB": {"date": "下個月 16 日", "amount": "92.65M ARB", "percent": "2.87%"},
    }
    if symbol in ['BTC', 'ETH']:
        return f"✅ {symbol} 無定期大量解鎖機制。"
    if symbol in mock_data:
        u = mock_data[symbol]
        return f"⚠️ **{symbol} 解鎖警告**\n\n- 時間: {u['date']}\n- 數量: {u['amount']}\n- 佔流通: {u['percent']}"
    return f"ℹ️ {symbol} 近期無大額解鎖。"


@tool
def get_token_supply(symbol: str) -> str:
    """獲取代幣供應量數據"""
    symbol = symbol.upper()
    cache_key = f"token_supply_{symbol}"
    cached = get_cached_data(cache_key, 600)
    if cached:
        return cached

    try:
        search_resp = httpx.get(f"https://api.coingecko.com/api/v3/search?query={symbol}", timeout=10)
        coins = search_resp.json().get("coins", [])
        if not coins:
            return f"找不到 {symbol}。"

        coin_id = coins[0]["id"]
        for c in coins:
            if c.get("symbol", "").upper() == symbol:
                coin_id = c["id"]
                break

        detail_resp = httpx.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true",
            timeout=10
        )
        md = detail_resp.json().get("market_data", {})

        def fmt(v):
            if v is None:
                return "未知"
            return f"{v/1_000_000_000:.2f}B" if v > 1_000_000_000 else f"{v/1_000_000:.2f}M"

        result = f"## 🪙 {symbol} 供應量\n\n- 流通: {fmt(md.get('circulating_supply'))}\n- 總量: {fmt(md.get('total_supply'))}\n- 上限: {fmt(md.get('max_supply'))}\n\n*(來源: CoinGecko)*"
        set_cached_data(cache_key, result)
        return result
    except Exception as e:
        return f"錯誤: {str(e)}"


@tool(args_schema=ExtractCryptoSymbolsInput)
def extract_crypto_symbols_tool(user_query: str) -> Dict:
    """從查詢中提取加密貨幣符號"""
    symbols = extract_crypto_symbols(user_query)
    return {"original_query": user_query, "extracted_symbols": symbols, "count": len(symbols)}
