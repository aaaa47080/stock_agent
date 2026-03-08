"""
Etherscan 工具
ETH Balance, ERC20 Balance, Address Transactions, Contract Info, ETH Price

設計原則：
- ⚠️ Etherscan API 需要 API Key，且有呼叫次數限制（100,000次/天）
- ⚠️ 公開平台不適合共享 API Key（會快速用完配額）
- ✅ 改為引導用戶到 Etherscan 網站自行查詢
"""
from langchain_core.tools import tool


@tool
def get_eth_balance(address: str) -> str:
    """查詢 Ethereum 地址的 ETH 餘額 - 引導用戶到 Etherscan"""
    if not address.startswith("0x") or len(address) != 42:
        return "❌ 無效的以太坊地址格式。地址應以 0x 開頭，長度為 42 字符。"

    return f"""## 💰 ETH 餘額查詢

**地址**: `{address}`

> 💡 **請前往 Etherscan 查詢**:
>
> 🔗 [點此查看餘額](https://etherscan.io/address/{address})
>
> Etherscan 提供完整的地址資訊：
> - ETH 餘額
> - ERC20 代幣餘額
> - NFT 持有
> - 交易歷史
> - 合約互動記錄

**為什麼不能直接查詢？**
Etherscan API 需要 API Key 且有配額限制（100,000次/天），
公開平台共享 Key 會快速用完配額，建議直接使用官網查詢。"""


@tool
def get_erc20_token_balance(address: str, contract_address: str) -> str:
    """查詢 Ethereum 地址的 ERC20 代幣餘額 - 引導用戶到 Etherscan"""
    if not address.startswith("0x") or len(address) != 42:
        return "❌ 無效的錢包地址格式"
    if not contract_address.startswith("0x") or len(contract_address) != 42:
        return "❌ 無效的合約地址格式"

    return f"""## 🪙 ERC20 代幣餘額查詢

**錢包地址**: `{address}`
**代幣合約**: `{contract_address}`

> 💡 **請前往 Etherscan 查詢**:
>
> 🔗 [點此查看代幣餘額](https://etherscan.io/token/{contract_address}?a={address})
>
> 或使用以下工具：
> - [DeBank](https://debank.com) - 多鏈資產總覽
> - [Zerion](https://zerion.io) - DeFi 資產追蹤
> - [MetaMask] - 錢包內直接查看"""


@tool
def get_address_transactions(address: str, limit: int = 10) -> str:
    """查詢 Ethereum 地址的最近交易記錄 - 引導用戶到 Etherscan"""
    if not address.startswith("0x") or len(address) != 42:
        return "❌ 無效的以太坊地址格式"

    return f"""## 📜 交易記錄查詢

**地址**: `{address}`

> 💡 **請前往 Etherscan 查看交易**:
>
> 🔗 [點此查看交易記錄](https://etherscan.io/address/{address})
>
> Etherscan 提供：
> - 完整交易歷史
> - ERC20 轉帳記錄
> - 失敗交易詳情
> - Gas 費用分析

**進階工具推薦**:
| 工具 | 網址 | 特點 |
|---|---|---|
| Etherscan | [etherscan.io](https://etherscan.io) | 官方區塊瀏覽器 |
| Dune Analytics | [dune.com](https://dune.com) | SQL 查詢交易 |
| Nansen | [nansen.ai](https://nansen.ai) | 智能地址標籤 |"""


@tool
def get_contract_info(contract_address: str) -> str:
    """查詢 Ethereum 智能合約的基本資訊 - 引導用戶到 Etherscan"""
    if not contract_address.startswith("0x") or len(contract_address) != 42:
        return "❌ 無效的合約地址格式"

    return f"""## 📄 智能合約資訊

**合約地址**: `{contract_address}`

> 💡 **請前往 Etherscan 查看合約**:
>
> 🔗 [點此查看合約詳情](https://etherscan.io/address/{contract_address})
>
> Etherscan 提供：
> - 合約創建者
> - 創建交易
> - 合約代碼（如已驗證）
> - 讀取/寫入合約功能
> - 事件日誌

**安全提示**:
⚠️ 與未知合約互動前，請確認：
1. 合約是否已驗證（Verified）
2. 是否通過安全審計
3. 社群評價如何"""


@tool
def get_eth_price_from_etherscan() -> str:
    """獲取 ETH 即時價格 - 使用免費 API"""
    import httpx

    try:
        # 使用 CoinGecko 免費 API（無需 Key）
        resp = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd,btc&include_24hr_change=true",
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json().get("ethereum", {})
            usd = data.get("usd", "N/A")
            btc = data.get("btc", "N/A")
            change = data.get("usd_24h_change", 0)

            change_emoji = "📈" if change > 0 else "📉"
            return f"""## 💎 ETH 即時價格

| 幣種 | 價格 |
|---|---|
| USD | ${usd:,.2f} |
| BTC | ₿{btc:.6f} |

{change_emoji} **24h 變化**: {change:+.2f}%

*(來源: CoinGecko)*"""

        return "無法取得 ETH 價格，請稍後再試"
    except Exception as e:
        return f"查詢失敗: {str(e)}"
