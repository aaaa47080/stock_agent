"""
DexScreener 工具
DEX Pair Info, Trending Pairs, Search Pairs
"""
from typing import List
from langchain_core.tools import tool
import httpx

from .common import DEXSCREENER_BASE


@tool
def get_dex_pair_info(token_address: str) -> dict:
    """獲取 DEX 代幣對的詳細資訊"""
    try:
        url = f"{DEXSCREENER_BASE}/dex/tokens/{token_address}"
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get("pairs", [])

            if not pairs:
                return {"error": "找不到此代幣的交易對"}

            # 選擇流動性最高的交易對
            best_pair = max(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0)

            base_token = best_pair.get("baseToken", {})
            quote_token = best_pair.get("quoteToken", {})

            return {
                "symbol": base_token.get("symbol", "Unknown"),
                "name": base_token.get("name", "Unknown"),
                "price_usd": best_pair.get("priceUsd", "N/A"),
                "price_native": best_pair.get("priceNative", "N/A"),
                "chain": best_pair.get("chainId", "Unknown"),
                "dex": best_pair.get("dexId", "Unknown"),
                "liquidity_usd": best_pair.get("liquidity", {}).get("usd", 0),
                "volume_24h": best_pair.get("volume", {}).get("h24", 0),
                "price_change_24h": best_pair.get("priceChange", {}).get("h24", 0),
                "pair_address": best_pair.get("pairAddress", ""),
                "url": best_pair.get("url", ""),
                "source": "DexScreener"
            }

        return {"error": f"API 錯誤: {resp.status_code}"}
    except Exception as e:
        return {"error": f"查詢失敗: {str(e)}"}


@tool
def get_trending_dex_pairs(chain_id: str = "") -> list:
    """獲取熱門 DEX 交易對"""
    try:
        url = f"{DEXSCREENER_BASE}/dex/profiles"
        if chain_id:
            url += f"?chainId={chain_id}"

        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            profiles = data.get("profiles", []) or data if isinstance(data, list) else []

            results = []
            for profile in profiles[:10]:
                results.append({
                    "chain": profile.get("chainId", ""),
                    "dex": profile.get("dexId", ""),
                    "pair": profile.get("pairAddress", "")[:10] + "...",
                    "symbol": profile.get("baseToken", {}).get("symbol", ""),
                })

            return results

        return [{"error": f"API 錯誤: {resp.status_code}"}]
    except Exception as e:
        return [{"error": f"查詢失敗: {str(e)}"}]


@tool
def search_dex_pairs(query: str) -> list:
    """搜索 DEX 交易對"""
    try:
        url = f"{DEXSCREENER_BASE}/dex/search?q={query}"
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get("pairs", [])

            results = []
            seen_symbols = set()

            for pair in pairs[:15]:
                base_token = pair.get("baseToken", {})
                symbol = base_token.get("symbol", "")

                if symbol in seen_symbols:
                    continue
                seen_symbols.add(symbol)

                results.append({
                    "chain": pair.get("chainId", ""),
                    "dex": pair.get("dexId", ""),
                    "pair_address": pair.get("pairAddress", ""),
                    "base_token": symbol,
                    "base_token_name": base_token.get("name", ""),
                    "quote_token": pair.get("quoteToken", {}).get("symbol", ""),
                    "price_usd": pair.get("priceUsd", ""),
                    "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
                    "volume_24h_usd": pair.get("volume", {}).get("h24", {}).get("usd", 0) if isinstance(pair.get("volume", {}).get("h24"), dict) else pair.get("volume", {}).get("h24", 0),
                    "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
                    "url": pair.get("url", ""),
                })

            return results

        return [{"error": f"API 錯誤: {resp.status_code}"}]
    except Exception as e:
        return [{"error": f"搜索失敗: {str(e)}"}]
