import sys
import os
import json
from datetime import datetime
from trading.okx_api_connector import OKXAPIConnector
from typing import List, Dict

# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import MINIMUM_INVESTMENT_USD, EXCHANGE_MINIMUM_ORDER_USD

def execute_trades_from_decision_data(decision_data: List[Dict], live_trading: bool = False):
    """
    Executes trades based on a list of decision data from the backend analyzer.

    Args:
        decision_data: A list of dictionaries, where each dictionary is a trading decision.
        live_trading: A flag to enable or disable actual trading.
    """
    print(f"[TRADE] Processing {len(decision_data)} trade decisions.")

    if not live_trading:
        print("[INFO] Live trading is disabled. Running in simulation mode.")
        return

    okx_api = OKXAPIConnector()
    if not all([okx_api.api_key, okx_api.secret_key, okx_api.passphrase]):
        print("[ERROR] OKX API credentials are not set. Cannot execute trades.")
        return

    if not okx_api.test_connection():
        print("[ERROR] Failed to connect to OKX API.")
        return

    print("[SUCCESS] OKX API connection successful.")

    for decision in decision_data:
        process_single_trade(okx_api, decision.get("spot_decision"))
        process_single_trade(okx_api, decision.get("futures_decision"))

def process_single_trade(okx_api: OKXAPIConnector, trade_decision: Dict):
    """
    Processes a single trade decision for either spot or futures market.
    """
    if not trade_decision or not trade_decision.get("should_trade"):
        print(f"[INFO] No trade advised for {trade_decision.get('market_type', 'unknown')}. Reason: {trade_decision.get('reasoning', 'Not specified')}")
        return

    investment_amount = trade_decision.get("investment_amount_usdt", 0)
    
    if investment_amount < MINIMUM_INVESTMENT_USD:
        print(f"[INFO] Investment amount ${investment_amount:.2f} is below the minimum threshold of ${MINIMUM_INVESTMENT_USD:.2f}. Skipping trade.")
        return

    market_type = trade_decision.get("market_type")
    symbol = trade_decision.get("symbol_for_trade")
    action = trade_decision.get("action")
    
    if not symbol:
         print(f"[ERROR] Symbol not provided in trade decision for {market_type}. Cannot proceed.")
         return

    print(f"\n[TRADE] Executing {market_type} trade for {symbol}")
    print(f"        Action: {action}, Amount: {investment_amount} USDT")

    if market_type == "spot":
        execute_spot_trade(okx_api, symbol, action, trade_decision)
    elif market_type == "futures":
        execute_futures_trade(okx_api, symbol, action, trade_decision)
    else:
        print(f"[ERROR] Unsupported market type: {market_type}")


def execute_spot_trade(okx_api: OKXAPIConnector, symbol: str, action: str, trade_data: dict):
    """
    Executes a spot trade on OKX.
    """
    if action not in ["buy", "sell"]:
        print(f"[INFO] No action required for spot trade. Action: {action}")
        return

    usd_amount = trade_data.get("investment_amount_usdt", 0)
    if usd_amount < EXCHANGE_MINIMUM_ORDER_USD:
        print(f"[ERROR] Investment amount ${usd_amount:.2f} is below the exchange minimum of ${EXCHANGE_MINIMUM_ORDER_USD:.2f}.")
        return

    # 需要通過市價買入金額計算購買數量
    if action == 'buy':
        # 獲取當前價格以計算購買數量
        ticker = okx_api.get_ticker(symbol)
        if ticker.get("code") != "0" or not ticker.get("data"):
            print(f"[ERROR] Could not retrieve ticker for {symbol} to calculate quantity.")
            return

        last_price = float(ticker["data"][0]["last"])
        if last_price <= 0:
            print(f"[ERROR] Invalid price ({last_price}) for {symbol}. Cannot calculate quantity.")
            return

        sz = usd_amount / last_price
        print(f"[INFO] Placing SPOT {action.upper()} order for {symbol} with {usd_amount} USDT ({sz} units).")

        order_result = okx_api.place_spot_order(
            instId=symbol,
            side=action,
            ordType="market",
            sz=str(round(sz, 6))  # 四捨五入到6位小數
        )
    else:  # sell
        # 對於賣出，需要先獲取持倉數量
        # 獲取當前價格以計算賣出數量
        ticker = okx_api.get_ticker(symbol)
        if ticker.get("code") != "0" or not ticker.get("data"):
            print(f"[ERROR] Could not retrieve ticker for {symbol} to calculate sell quantity.")
            return

        last_price = float(ticker["data"][0]["last"])
        if last_price <= 0:
            print(f"[ERROR] Invalid price ({last_price}) for {symbol}. Cannot calculate sell quantity.")
            return

        # 獲取帳戶資產以確定可賣出數量
        asset_symbol = symbol.split('-')[0]  # 從 "PIUSDT" 或 "PI-USDT" 中提取 "PI"
        balance_result = okx_api.get_account_balance(asset_symbol)

        if balance_result.get("code") != "0" or not balance_result.get("data"):
            print(f"[ERROR] Could not retrieve balance for {asset_symbol} to determine sell amount.")
            return

        details = balance_result["data"][0].get("details", [])
        if not details:
            print(f"[ERROR] No balance details available for {asset_symbol}.")
            return

        available_amount = float(details[0].get("availBal", 0))
        if available_amount <= 0:
            print(f"[ERROR] Insufficient balance of {asset_symbol} to sell. Available: {available_amount}")
            return

        # 計算要賣出的數量 (使用全部可賣出數量或根據投資策略計算的數量)
        desired_sell_amount = min(available_amount, usd_amount / last_price) if last_price > 0 else available_amount
        sz = desired_sell_amount

        print(f"[INFO] Placing SPOT {action.upper()} order for {symbol} selling {sz} units (available: {available_amount}).")

        order_result = okx_api.place_spot_order(
            instId=symbol,
            side=action,
            ordType="market",
            sz=str(round(sz, 6))  # 四捨五入到6位小數
        )

    print(f"[ORDER] Spot order result: {order_result}")
    if order_result.get("code") == "0":
        print(f"[SUCCESS] Spot {action.upper()} order placed successfully for {symbol}.")
    else:
        print(f"[ERROR] Failed to place spot order for {symbol}. Reason: {order_result.get('msg')}")

def execute_futures_trade(okx_api: OKXAPIConnector, symbol: str, action: str, trade_data: dict):
    """
    Executes a futures trade on OKX.
    """
    pos_side = None
    if action == "long":
        side = "buy"
        pos_side = "long"
    elif action == "short":
        side = "sell"
        pos_side = "short"
    else:
        print(f"[INFO] No action required for futures trade. Action: {action}")
        return

    if not symbol.endswith("-SWAP"):
        futures_symbol = f"{symbol}-SWAP"
    else:
        futures_symbol = symbol

    leverage = trade_data.get("leverage", 10)
    leverage_result = okx_api.set_leverage(instId=futures_symbol, lever=str(leverage), mgnMode="cross")
    if leverage_result.get("code") != "0":
        print(f"[ERROR] Failed to set leverage for {futures_symbol}. Reason: {leverage_result.get('msg')}")
        return

    print(f"[INFO] Leverage for {futures_symbol} set to {leverage}x.")

    usd_amount = trade_data.get("investment_amount_usdt", 0)
    if usd_amount < EXCHANGE_MINIMUM_ORDER_USD:
        print(f"[ERROR] Investment amount ${usd_amount:.2f} is below the exchange minimum of ${EXCHANGE_MINIMUM_ORDER_USD:.2f}.")
        return

    ticker = okx_api.get_ticker(futures_symbol)
    if ticker.get("code") != "0" or not ticker.get("data"):
        print(f"[ERROR] Could not retrieve ticker for {futures_symbol} to calculate contract size.")
        return
    
    last_price = float(ticker["data"][0]["last"])
    if last_price <= 0:
        print(f"[ERROR] Invalid price ({last_price}) for {futures_symbol}. Cannot calculate contract size.")
        return
        
    sz = usd_amount / last_price

    print(f"[INFO] Placing FUTURES {action.upper()} order for {futures_symbol} with {usd_amount} USDT ({sz} contracts).")
    
    order_result = okx_api.place_futures_order(
        instId=futures_symbol,
        side=side,
        posSide=pos_side,
        ordType="market",
        sz=str(round(sz, 6)),
        lever=str(leverage)
    )

    print(f"[ORDER] Futures order result: {order_result}")
    if order_result.get("code") == "0":
        print(f"[SUCCESS] Futures {action.upper()} order placed successfully for {futures_symbol}.")
    else:
        print(f"[ERROR] Failed to place futures order. Reason: {order_result.get('msg')}")


def execute_trade_from_analysis_file(json_file_path: str, live_trading: bool = False):
    """
    Loads trade decisions from a JSON file and executes them.
    """
    print(f"[TRADE] Reading analysis from: {json_file_path}")
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            decision_data = json.load(f)
        
        if isinstance(decision_data, dict):
            decision_data = [decision_data]

        execute_trades_from_decision_data(decision_data, live_trading)

    except FileNotFoundError:
        print(f"[ERROR] Analysis file not found: {json_file_path}")
    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON in file: {json_file_path}")