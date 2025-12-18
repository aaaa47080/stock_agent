import sys
import os
import json
from datetime import datetime
from trading.okx_api_connector import OKXAPIConnector
from typing import List, Dict

# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import MINIMUM_INVESTMENT_USD, EXCHANGE_MINIMUM_ORDER_USD, ENABLE_SPOT_TRADING, ENABLE_FUTURES_TRADING

def execute_trades_from_decision_data(decision_data: List[Dict], live_trading: bool = False):
    """
    Executes trades based on a list of decision data from the backend analyzer.

    Args:
        decision_data: A list of dictionaries, where each dictionary is a trading decision.
        live_trading: A flag to enable or disable actual trading.
    """
    print(f"[TRADE] Processing {len(decision_data)} trade decisions.")
    print(f"[CONFIG] Spot Trading: {'Enabled' if ENABLE_SPOT_TRADING else 'Disabled'}")
    print(f"[CONFIG] Futures Trading: {'Enabled' if ENABLE_FUTURES_TRADING else 'Disabled'}")

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
        # 根據配置決定是否執行現貨交易
        if ENABLE_SPOT_TRADING:
            process_single_trade(okx_api, decision.get("spot_decision"))
        else:
            print("[INFO] Spot trading is disabled in config. Skipping spot decision.")

        # 根據配置決定是否執行合約交易
        if ENABLE_FUTURES_TRADING:
            process_single_trade(okx_api, decision.get("futures_decision"))
        else:
            print("[INFO] Futures trading is disabled in config. Skipping futures decision.")

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

        # 獲取交易規則以確定最小數量和精度
        inst_info = okx_api.get_instruments("SPOT", symbol)
        min_sz = 1  # 默認最小數量
        lot_sz = 0.000001  # 默認精度

        if inst_info.get("code") == "0" and inst_info.get("data"):
            inst_data = inst_info["data"][0]
            min_sz = float(inst_data.get("minSz", 1))
            lot_sz = float(inst_data.get("lotSz", 0.000001))
            print(f"[INFO] Trading rules for {symbol}: minSz={min_sz}, lotSz={lot_sz}")

        # 預留 0.2% 作為手續費 (maker fee 通常約 0.08-0.1%, 多留餘地)
        effective_amount = usd_amount * 0.998
        sz = effective_amount / last_price

        # 確保數量符合 lot size 規則 (向下取整到 lot size 的倍數)
        sz = int(sz / lot_sz) * lot_sz

        # 確保數量不低於最小數量
        if sz < min_sz:
            print(f"[ERROR] Calculated quantity {sz} is below minimum {min_sz} for {symbol}.")
            return

        print(f"[INFO] Placing SPOT {action.upper()} order for {symbol} with {effective_amount:.2f} USDT ({sz} units).")

        order_result = okx_api.place_spot_order(
            instId=symbol,
            side=action,
            ordType="market",
            sz=str(sz)
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
    # Get account position mode to determine correct posSide value
    account_config = okx_api.get_account_config()
    pos_mode = "net_mode"  # Default to net_mode

    if account_config.get("code") == "0" and account_config.get("data"):
        pos_mode = account_config["data"][0].get("posMode", "net_mode")
        print(f"[INFO] Account position mode: {pos_mode}")

    # Set side and posSide based on action and position mode
    pos_side = None
    if action == "long":
        side = "buy"
        # In net_mode, use 'net'; in long_short_mode, use 'long'
        pos_side = "net" if pos_mode == "net_mode" else "long"
    elif action == "short":
        side = "sell"
        # In net_mode, use 'net'; in long_short_mode, use 'short'
        pos_side = "net" if pos_mode == "net_mode" else "short"
    else:
        print(f"[INFO] No action required for futures trade. Action: {action}")
        return

    if not symbol.endswith("-SWAP"):
        futures_symbol = f"{symbol}-SWAP"
    else:
        futures_symbol = symbol

    leverage = trade_data.get("leverage", 10)
    print(f"[INFO] Setting leverage for {futures_symbol} to {leverage}x with posSide={pos_side}.")

    # Try to set leverage with posSide parameter for position mode compatibility
    leverage_result = okx_api.set_leverage(instId=futures_symbol, lever=str(leverage), mgnMode="cross", posSide=pos_side)
    if leverage_result.get("code") != "0":
        print(f"[WARNING] Failed to set leverage for {futures_symbol}. Reason: {leverage_result.get('msg')}")
        print(f"[INFO] This might be because leverage is already set or the instrument doesn't require leverage setting. Continuing with trade...")
    else:
        print(f"[INFO] Leverage for {futures_symbol} set to {leverage}x successfully.")

    margin_amount = trade_data.get("investment_amount_usdt", 0)  # 保證金金額
    if margin_amount < EXCHANGE_MINIMUM_ORDER_USD:
        print(f"[ERROR] Margin amount ${margin_amount:.2f} is below the exchange minimum of ${EXCHANGE_MINIMUM_ORDER_USD:.2f}.")
        return

    ticker = okx_api.get_ticker(futures_symbol)
    if ticker.get("code") != "0" or not ticker.get("data"):
        print(f"[ERROR] Could not retrieve ticker for {futures_symbol} to calculate contract size.")
        return

    last_price = float(ticker["data"][0]["last"])
    if last_price <= 0:
        print(f"[ERROR] Invalid price ({last_price}) for {futures_symbol}. Cannot calculate contract size.")
        return

    # 獲取合約交易規則
    inst_info = okx_api.get_instruments("SWAP", futures_symbol)
    ct_val = 1  # 默認合約面值
    lot_sz = 1  # 默認張數最小單位
    min_sz = 1  # 默認最小張數

    if inst_info.get("code") == "0" and inst_info.get("data"):
        inst_data = inst_info["data"][0]
        ct_val = float(inst_data.get("ctVal", 1))  # 合約面值 (例如: 1 表示 1 張合約 = 1 幣)
        lot_sz = float(inst_data.get("lotSz", 1))  # 下單數量精度
        min_sz = float(inst_data.get("minSz", 1))  # 最小下單數量
        print(f"[INFO] Trading rules for {futures_symbol}: ctVal={ct_val}, lotSz={lot_sz}, minSz={min_sz}")

    # === 重要修正：合約張數計算需要考慮槓桿 ===
    # 合約價值 = 保證金 × 槓桿
    # 例如：保證金100美元，10倍槓桿 = 開1000美元的倉位
    #
    # 手續費預留：OKX 合約手續費約 0.02% (maker) ~ 0.05% (taker)
    # 使用市價單(taker)，預留 0.06% 的手續費
    FEE_RATE = 0.0006  # 0.06%
    effective_margin = margin_amount * (1 - FEE_RATE)  # 扣除手續費後的有效保證金

    # 計算合約總價值 = 有效保證金 × 槓桿
    contract_value_usd = effective_margin * leverage

    # 計算合約張數 = 合約總價值 / (價格 × 合約面值)
    # 對於 PI-USDT-SWAP: 1 張合約 = 1 PI，ct_val = 1
    # 如果價格是 0.2 USDT/PI，要開1000 USDT的倉位，需要 1000/(0.2*1) = 5000 張
    sz = contract_value_usd / (last_price * ct_val)

    # 確保數量符合 lot size 規則 (向下取整到 lot size 的倍數)
    # OKX 合約通常要求整數張，所以向下取整
    sz = int(sz / lot_sz) * lot_sz

    # 確保數量不低於最小數量
    if sz < min_sz:
        print(f"[ERROR] Calculated contract size {sz} is below minimum {min_sz} for {futures_symbol}.")
        return

    # 从 trade_data 中提取止损止盈价格
    stop_loss = trade_data.get("stop_loss")
    take_profit = trade_data.get("take_profit")

    print(f"[INFO] Futures Order Details:")
    print(f"        Margin: ${margin_amount:.2f} USDT")
    print(f"        Leverage: {leverage}x")
    print(f"        Contract Value: ${contract_value_usd:.2f} USDT ({int(sz)} contracts)")
    print(f"        Entry Price: ${last_price:.4f}")
    if stop_loss:
        print(f"        Stop Loss: ${stop_loss:.4f}")
    if take_profit:
        print(f"        Take Profit: ${take_profit:.4f}")
    print(f"[INFO] Placing FUTURES {action.upper()} order for {futures_symbol}...")

    order_result = okx_api.place_futures_order(
        instId=futures_symbol,
        side=side,
        posSide=pos_side,
        ordType="market",
        sz=str(int(sz)),  # 確保是整數
        lever=str(leverage),
        slTriggerPx=str(stop_loss) if stop_loss else None,
        tpTriggerPx=str(take_profit) if take_profit else None
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