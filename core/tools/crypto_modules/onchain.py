"""
鏈上數據工具
Gas Fees, Whale Transactions, Exchange Flow
"""
from langchain_core.tools import tool
import httpx

from .common import get_cached_data, set_cached_data


@tool
def get_gas_fees() -> str:
    """獲取 Ethereum 網路的即時 Gas 費用"""
    try:
        resp = httpx.get("https://api.etherscan.io/api?module=gastracker&action=gasoracle", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "1":
                result = data.get("result", {})
                return f"""## ⛽ Ethereum Gas 費用

| 等級 | Gwei | 適用 |
|---|---|---|
| 🐢 慢 | {result.get('SafeGasPrice')} | 不急 |
| 🚗 標準 | {result.get('ProposeGasPrice')} | 一般 |
| 🚀 快 | {result.get('FastGasPrice')} | 搶時 |

*(來源: Etherscan)*"""
        return "無法取得 Gas 數據。"
    except Exception as e:
        return f"錯誤: {str(e)}"


@tool
def get_whale_transactions(symbol: str = "BTC", min_value_usd: int = 500000) -> str:
    """獲取大額鏈上轉帳（鯨魚交易）"""
    symbol = symbol.upper()
    cache_key = f"whale_tx_{symbol}"
    cached = get_cached_data(cache_key, 120)
    if cached:
        return cached

    try:
        if symbol == "BTC":
            resp = httpx.get("https://blockchain.com/blocks/unconfirmed-transactions?format=json", timeout=15)
            if resp.status_code == 200:
                txs = resp.json().get("txs", [])[:20]
                whale_txs = []
                btc_price = 45000  # Approximate

                for tx in txs:
                    for out in tx.get("out", []):
                        value_btc = out.get("value", 0) / 100_000_000
                        value_usd = value_btc * btc_price
                        if value_usd >= min_value_usd:
                            whale_txs.append({
                                "hash": tx.get("hash", "")[:16] + "...",
                                "value_btc": value_btc,
                                "value_usd": value_usd
                            })

                if whale_txs:
                    result = f"## 🐋 BTC 鯨魚交易 (>{min_value_usd/1_000_000:.1f}M USD)\n\n"
                    for i, tx in enumerate(whale_txs[:5], 1):
                        result += f"{i}. {tx['value_btc']:.4f} BTC (~${tx['value_usd']/1_000_000:.1f}M)\n"
                    result += "\n*(來源: Blockchain.com)*"
                    set_cached_data(cache_key, result)
                    return result
                return "近期無大額 BTC 轉帳。"
        return f"目前僅支援 BTC。"
    except Exception as e:
        return f"錯誤: {str(e)}"


@tool
def get_exchange_flow(symbol: str = "BTC") -> str:
    """獲取交易所資金流向"""
    symbol = symbol.upper()
    cache_key = f"exchange_flow_{symbol}"
    cached = get_cached_data(cache_key, 300)
    if cached:
        return cached

    # Mock data for demonstration
    mock_flows = {
        "BTC": {"net_flow": "-12,500 BTC", "trend": "淨流出 (利多)", "detail": "過去 24 小時從交易所提走 12,500 BTC"},
        "ETH": {"net_flow": "-8,200 ETH", "trend": "淨流出 (利多)", "detail": "過去 24 小時從交易所提走 8,200 ETH"},
    }

    if symbol in mock_flows:
        flow = mock_flows[symbol]
        result = f"""## 🏦 {symbol} 交易所資金流向

- **淨流量**: {flow['net_flow']}
- **趨勢**: {flow['trend']}
- **說明**: {flow['detail']}

> 淨流出 = 從交易所提幣 = 潛在賣壓減少 = 利多
> 淨流入 = 存入交易所 = 潛在賣壓增加 = 利空

*(來源: CryptoQuant 模擬數據)*"""
        set_cached_data(cache_key, result)
        return result

    return f"目前無 {symbol} 的交易所流向數據。"
