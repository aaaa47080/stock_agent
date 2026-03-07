"""
Etherscan 工具
ETH Balance, ERC20 Balance, Address Transactions, Contract Info, ETH Price
"""
import os
from langchain_core.tools import tool
import httpx


# 從環境變數獲取 API Key（可選）
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "YourApiKeyToken")
ETHERSCAN_BASE = f"https://api.etherscan.io/api?apikey={ETHERSCAN_API_KEY}"


@tool
def get_eth_balance(address: str) -> dict:
    """查詢 Ethereum 地址的 ETH 餘額"""
    if not address.startswith("0x") or len(address) != 42:
        return {"error": "無效的以太坊地址格式"}

    try:
        url = f"{ETHERSCAN_BASE}&module=account&action=balance&address={address}&tag=latest"
        resp = httpx.get(url, timeout=10)

        if resp.status_code != 200:
            return {"error": f"API 錯誤: {resp.status_code}"}

        data = resp.json()
        if data.get("status") != "1":
            return {"error": data.get("message", "查詢失敗")}

        balance_wei = int(data.get("result", 0))
        balance_eth = balance_wei / 1e18

        return {
            "address": address,
            "balance_eth": round(balance_eth, 6),
            "explorer_url": f"https://etherscan.io/address/{address}",
            "source": "Etherscan"
        }
    except Exception as e:
        return {"error": f"查詢失敗: {str(e)}"}


@tool
def get_erc20_token_balance(address: str, contract_address: str) -> dict:
    """查詢 Ethereum 地址的 ERC20 代幣餘額"""
    try:
        url = f"{ETHERSCAN_BASE}&module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest"
        resp = httpx.get(url, timeout=10)

        if resp.status_code != 200:
            return {"error": f"API 錯誤: {resp.status_code}"}

        data = resp.json()
        if data.get("status") != "1":
            return {"error": data.get("message", "查詢失敗")}

        balance_raw = int(data.get("result", 0))
        balance = balance_raw / 1e18  # Assuming 18 decimals

        return {
            "wallet_address": address,
            "contract_address": contract_address,
            "balance": round(balance, 4),
            "explorer_url": f"https://etherscan.io/token/{contract_address}?a={address}",
            "source": "Etherscan"
        }
    except Exception as e:
        return {"error": f"查詢失敗: {str(e)}"}


@tool
def get_address_transactions(address: str, limit: int = 10) -> dict:
    """查詢 Ethereum 地址的最近交易記錄"""
    limit = min(limit, 50)

    try:
        url = f"{ETHERSCAN_BASE}&module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset={limit}&sort=desc"
        resp = httpx.get(url, timeout=15)

        if resp.status_code != 200:
            return {"error": f"API 錯誤: {resp.status_code}"}

        data = resp.json()
        if data.get("status") != "1":
            return {"error": data.get("message", "查詢失敗"), "note": "可能該地址沒有交易記錄"}

        transactions = data.get("result", [])
        formatted_txs = []

        for tx in transactions:
            value_wei = int(tx.get("value", 0))
            value_eth = value_wei / 1e18
            is_sent = tx.get("from", "").lower() == address.lower()

            formatted_txs.append({
                "hash": tx.get("hash", "")[:16] + "...",
                "timestamp": tx.get("timeStamp", ""),
                "direction": "發送" if is_sent else "接收",
                "value_eth": round(value_eth, 6),
                "tx_url": f"https://etherscan.io/tx/{tx.get('hash', '')}"
            })

        return {
            "address": address,
            "total": len(formatted_txs),
            "transactions": formatted_txs,
            "source": "Etherscan"
        }
    except Exception as e:
        return {"error": f"查詢失敗: {str(e)}"}


@tool
def get_contract_info(contract_address: str) -> dict:
    """查詢 Ethereum 智能合約的基本資訊"""
    try:
        url = f"{ETHERSCAN_BASE}&module=contract&action=getcontractcreation&contractaddresses={contract_address}"
        resp = httpx.get(url, timeout=10)

        contract_info = {
            "address": contract_address,
            "explorer_url": f"https://etherscan.io/address/{contract_address}",
            "source": "Etherscan"
        }

        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "1" and data.get("result"):
                creation_info = data["result"][0]
                contract_info["creator"] = creation_info.get("contractCreator", "")
                contract_info["tx_hash"] = creation_info.get("txHash", "")

        return contract_info
    except Exception as e:
        return {"error": f"查詢失敗: {str(e)}"}


@tool
def get_eth_price_from_etherscan() -> dict:
    """從 Etherscan 獲取 ETH 即時價格"""
    try:
        url = f"{ETHERSCAN_BASE}&module=stats&action=ethprice"
        resp = httpx.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "1":
                result = data.get("result", {})
                return {
                    "eth_btc": result.get("ethbtc", "N/A"),
                    "eth_usd": result.get("ethusd", "N/A"),
                    "source": "Etherscan"
                }
        return {"error": "無法取得 ETH 價格"}
    except Exception as e:
        return {"error": f"查詢失敗: {str(e)}"}
