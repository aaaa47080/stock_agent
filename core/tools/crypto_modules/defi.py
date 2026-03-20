"""
DeFi 工具
DefiLlama TVL, Categories & Gainers, Token Unlocks, Token Supply
"""

from typing import Dict

import httpx
from langchain_core.tools import tool

from ..helpers import extract_crypto_symbols
from ..schemas import ExtractCryptoSymbolsInput
from .common import get_cached_data, set_cached_data


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
                tvl_str = (
                    f"${tvl / 1_000_000_000:.2f}B"
                    if tvl > 1_000_000_000
                    else f"${tvl / 1_000_000:.2f}M"
                )
                return f"## 🏦 DefiLlama TVL\n\n- **協議**: {name}\n- **TVL**: {tvl_str}\n\n*(來源: DefiLlama)*"

        # Try as chain
        chains_resp = httpx.get("https://api.llama.fi/v2/chains", timeout=10)
        if chains_resp.status_code == 200:
            for chain in chains_resp.json():
                if (
                    chain.get("name", "").lower() == slug
                    or chain.get("tokenSymbol", "").lower() == slug
                ):
                    tvl = chain.get("tvl", 0)
                    tvl_str = (
                        f"${tvl / 1_000_000_000:.2f}B"
                        if tvl > 1_000_000_000
                        else f"${tvl / 1_000_000:.2f}M"
                    )
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
        resp = httpx.get(
            "https://api.coingecko.com/api/v3/coins/categories", timeout=10
        )
        if resp.status_code == 200:
            categories = resp.json()
            sorted_cats = sorted(
                [c for c in categories if c.get("market_cap_change_24h") is not None],
                key=lambda x: x["market_cap_change_24h"],
                reverse=True,
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
    if symbol in ["BTC", "ETH"]:
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
        search_resp = httpx.get(
            f"https://api.coingecko.com/api/v3/search?query={symbol}", timeout=10
        )
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
            timeout=10,
        )
        md = detail_resp.json().get("market_data", {})

        def fmt(v):
            if v is None:
                return "未知"
            return (
                f"{v / 1_000_000_000:.2f}B"
                if v > 1_000_000_000
                else f"{v / 1_000_000:.2f}M"
            )

        result = f"## 🪙 {symbol} 供應量\n\n- 流通: {fmt(md.get('circulating_supply'))}\n- 總量: {fmt(md.get('total_supply'))}\n- 上限: {fmt(md.get('max_supply'))}\n\n*(來源: CoinGecko)*"
        set_cached_data(cache_key, result)
        return result
    except Exception as e:
        return f"錯誤: {str(e)}"


@tool(args_schema=ExtractCryptoSymbolsInput)
def extract_crypto_symbols_tool(user_query: str) -> Dict:
    """從查詢中提取加密貨幣符號"""
    symbols = extract_crypto_symbols(user_query)
    return {
        "original_query": user_query,
        "extracted_symbols": symbols,
        "count": len(symbols),
    }


@tool
def get_staking_yield(symbol: str) -> str:
    """獲取加密貨幣的質押年化收益率（APY）。

    使用 DefiLlama Yields API 獲取實時質押/借貸收益率數據。
    支援任何在 DeFi 協議中有質押池的代幣。
    """
    symbol = symbol.upper()
    cache_key = f"staking_yield_{symbol}"
    cached = get_cached_data(cache_key, 600)
    if cached:
        return cached

    try:
        # 使用 DefiLlama Yields API - 獲取所有質押池數據
        resp = httpx.get("https://yields.llama.fi/pools", timeout=15)

        if resp.status_code != 200:
            return "無法獲取質押收益率數據（API 錯誤）"

        all_pools = resp.json().get("data", [])

        # 篩選與該代幣相關的質押池
        # 优先級：原生質押 > LST > 借貸
        relevant_pools = []
        for pool in all_pools:
            pool_symbol = pool.get("symbol", "").upper()
            underlying = pool.get("underlyingTokens") or []  # 確保不是 None
            pool_name = pool.get("poolName", "").upper()
            chain = pool.get("chain", "")

            # 檢查是否匹配目標代幣
            is_match = (
                symbol == pool_symbol
                or symbol in pool_name
                or (underlying and any(symbol == t.upper() for t in underlying))
                or f"{symbol}2" in pool_symbol  # stETH, stSOL 等
                or f"S{symbol}" in pool_symbol
            )

            if is_match:
                apy = pool.get("apy", 0) or 0
                tvl = pool.get("tvlUsd", 0) or 0
                pool_type = (
                    pool.get("apyBaseBorrow", None) is not None and "借貸" or "質押"
                )
                if (
                    "stake" in pool.get("poolName", "").lower()
                    or "staking" in pool.get("poolName", "").lower()
                ):
                    pool_type = "原生質押"

                relevant_pools.append(
                    {
                        "pool": pool.get("poolName", "Unknown"),
                        "project": pool.get("project", ""),
                        "chain": chain,
                        "apy": apy,
                        "tvl": tvl,
                        "type": pool_type,
                    }
                )

        if not relevant_pools:
            # 嘗試通過 CoinGecko 獲取基本信息
            return _get_staking_info_from_coingecko(symbol)

        # 按 TVL 排序，優先顯示高 TVL 池
        relevant_pools.sort(key=lambda x: x["tvl"], reverse=True)

        # 取前 5 個池
        top_pools = relevant_pools[:5]

        result = f"## 💰 {symbol} 質押/借貸收益率\n\n"
        result += "| 協議 | 鏈 | 類型 | APY | TVL |\n"
        result += "|---|---|---|---|---|\n"

        for p in top_pools:
            tvl_str = (
                f"${p['tvl'] / 1_000_000:.1f}M"
                if p["tvl"] > 1_000_000
                else f"${p['tvl'] / 1_000:.0f}K"
            )
            result += f"| {p['project']} | {p['chain']} | {p['type']} | {p['apy']:.2f}% | {tvl_str} |\n"

        result += "\n> ⚠️ 收益率會隨市場變化，過去收益不代表未來。\n"
        result += "> 📊 數據來源: DefiLlama Yields\n"

        set_cached_data(cache_key, result)
        return result

    except Exception as e:
        return f"獲取質押收益率時發生錯誤: {str(e)}"


def _get_staking_info_from_coingecko(symbol: str) -> str:
    """從 CoinGecko 獲取代幣質押信息（備用方案）"""
    try:
        # 搜索代幣
        search_resp = httpx.get(
            f"https://api.coingecko.com/api/v3/search?query={symbol}", timeout=10
        )
        coins = search_resp.json().get("coins", [])

        if not coins:
            return f"找不到 {symbol} 的質押數據。請確認代幣符號是否正確。"

        coin_id = coins[0]["id"]
        for c in coins:
            if c.get("symbol", "").upper() == symbol:
                coin_id = c["id"]
                break

        # 獲取代幣詳細信息
        detail_resp = httpx.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=true",
            timeout=10,
        )

        if detail_resp.status_code != 200:
            return f"無法獲取 {symbol} 的詳細信息。"

        data = detail_resp.json()

        # 檢查是否有質押信息
        # CoinGecko 不直接提供質押 APY，返回基本信息
        result = f"## {symbol} 質押資訊\n\n"

        # 檢查共識機制
        categories = data.get("categories", [])
        is_pos = any(
            "proof-of-stake" in c.lower() or "pos" in c.lower() for c in categories
        )
        is_pow = any(
            "proof-of-work" in c.lower() or "pow" in c.lower() for c in categories
        )

        if is_pow or symbol.upper() in ["BTC", "DOGE", "LTC", "BCH"]:
            result += f"❌ {symbol} 使用工作量證明（PoW）機制，不支援原生質押。\n\n"
            result += "💡 **替代方案**:\n"
            result += "- 透過交易所理財產品（如 Binance Earn）獲取收益\n"
            result += "- 使用借貸協議（如 Aave、Compound）提供流動性\n"
        elif is_pos or symbol.upper() in [
            "ETH",
            "SOL",
            "ADA",
            "ATOM",
            "DOT",
            "MATIC",
            "AVAX",
            "NEAR",
            "SUI",
        ]:
            result += f"✅ {symbol} 支援原生質押。\n\n"
            result += "📊 **建議**: 使用 DefiLlama 或官方錢包查看即時質押收益率。\n"
            result += f"- 鏈: {data.get('asset_platform_id', 'Unknown')}\n"
        else:
            result += f"ℹ️ 未能確定 {symbol} 的質押支援狀態。\n"
            result += "請查看該項目的官方文檔了解質押選項。\n"

        return result

    except Exception as e:
        return f"獲取質押信息時發生錯誤: {str(e)}"
