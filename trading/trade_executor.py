import argparse
import glob
import os
import sys
import json
from typing import Optional, Dict

# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.okx_api_connector import OKXAPIConnector
from core.config import MINIMUM_INVESTMENT_USD, EXCHANGE_MINIMUM_ORDER_USD

class TradeExecutor:
    """
    Handles the execution of trades on OKX, calculating correct sizes and handling API interactions.
    """
    def __init__(self):
        self.okx = OKXAPIConnector()
        if not all([self.okx.api_key, self.okx.secret_key, self.okx.passphrase]):
            print("[WARNING] OKX API credentials missing. TradeExecutor initialized in limited mode.")

    def execute_spot(self, symbol: str, side: str, amount_usdt: float) -> Dict:
        """
        Executes a spot trade (Market Order).
        
        Args:
            symbol: e.g., "BTC-USDT"
            side: "buy" or "sell"
            amount_usdt: Amount in USDT to spend (for buy) or equivalent value to sell.
        """
        if amount_usdt < EXCHANGE_MINIMUM_ORDER_USD:
            return {"status": "failed", "error": f"Amount ${amount_usdt:.2f} below minimum ${EXCHANGE_MINIMUM_ORDER_USD}"}

        # 1. Get current price
        ticker = self.okx.get_ticker(symbol)
        if ticker.get("code") != "0" or not ticker.get("data"):
            return {"status": "failed", "error": f"Failed to get ticker for {symbol}"}
        
        last_price = float(ticker["data"][0]["last"])
        if last_price <= 0:
            return {"status": "failed", "error": f"Invalid price {last_price} for {symbol}"}

        # 2. Get Instrument Info (minSz, lotSz)
        inst_info = self.okx.get_instruments("SPOT", symbol)
        min_sz = 1.0
        lot_sz = 0.000001
        
        if inst_info.get("code") == "0" and inst_info.get("data"):
            inst_data = inst_info["data"][0]
            min_sz = float(inst_data.get("minSz", 1))
            lot_sz = float(inst_data.get("lotSz", 0.000001))

        # 3. Calculate Quantity (sz)
        if side == "buy":
            # For market buy, OKX 'sz' is the quote currency amount (USDT)
            # But we often need to be careful. OKX API v5:
            # Spot Market Buy: sz is Quote Currency amount (USDT).
            # Spot Market Sell: sz is Base Currency amount (BTC).
            
            # Let's double check OKX API docs behavior.
            # "ordType=market, side=buy, sz=amount in quote currency" -> Correct.
            
            # We just need to check if the RESULTING quantity (amount/price) >= minSz
            estimated_qty = amount_usdt / last_price
            if estimated_qty < min_sz:
                 return {"status": "failed", "error": f"Estimated quantity {estimated_qty} < minSz {min_sz}"}
            
            # For market buy, we pass the USDT amount directly as 'sz'
            # Note: We might want to truncate to avoid too many decimals, though Quote amount usually allows 2-4 decimals
            sz = str(amount_usdt)
            
        else: # sell
            # For sell, we need Base Currency Amount
            # We are given amount_usdt.
            base_amount = amount_usdt / last_price
            
            # Apply lot size (round down)
            base_amount = int(base_amount / lot_sz) * lot_sz
            
            if base_amount < min_sz:
                return {"status": "failed", "error": f"Calculated sell quantity {base_amount} < minSz {min_sz}"}
                
            sz = str(base_amount)

        print(f"[EXECUTOR] Placing Spot {side.upper()} {symbol}: sz={sz}")
        result = self.okx.place_spot_order(
            instId=symbol,
            side=side,
            ordType="market",
            sz=sz
        )
        
        if result.get("code") == "0":
            return {"status": "success", "details": result}
        else:
            return {"status": "failed", "error": result.get("msg")}

    def execute_futures(self, symbol: str, side: str, margin_amount: float, leverage: int = 5, stop_loss: float = None, take_profit: float = None) -> Dict:
        """
        Executes a futures trade (Market Order).
        
        Args:
            symbol: e.g., "BTC-USDT-SWAP"
            side: "long" or "short"
            margin_amount: Margin in USDT.
            leverage: Leverage multiplier.
        """
        if margin_amount < EXCHANGE_MINIMUM_ORDER_USD:
            return {"status": "failed", "error": f"Margin ${margin_amount:.2f} below minimum ${EXCHANGE_MINIMUM_ORDER_USD}"}

        if not symbol.endswith("-SWAP"):
            symbol = f"{symbol}-SWAP"

        # 1. Determine posSide & Order Side
        # Check Position Mode
        config = self.okx.get_account_config()
        pos_mode = "net_mode"
        if config.get("code") == "0" and config.get("data"):
            pos_mode = config["data"][0].get("posMode", "net_mode")
        
        order_side = ""
        pos_side = ""
        
        if side.lower() == "long":
            order_side = "buy"
            pos_side = "long" if pos_mode == "long_short_mode" else "net"
        elif side.lower() == "short":
            order_side = "sell"
            pos_side = "short" if pos_mode == "long_short_mode" else "net"
        else:
            return {"status": "failed", "error": f"Invalid side {side}"}

        # 2. Set Leverage
        self.okx.set_leverage(instId=symbol, lever=str(leverage), mgnMode="cross", posSide=pos_side)

        # 3. Calculate Contract Size (sz) - quantity in contracts (张)
        ticker = self.okx.get_ticker(symbol)
        if ticker.get("code") != "0": return {"status": "failed", "error": "Ticker failed"}
        last_price = float(ticker["data"][0]["last"])

        inst_info = self.okx.get_instruments("SWAP", symbol)
        if inst_info.get("code") != "0": return {"status": "failed", "error": "Instruments failed"}
        
        inst_data = inst_info["data"][0]
        ct_val = float(inst_data.get("ctVal", 1)) # Contract Value (e.g. 1 PI per contract)
        min_sz = float(inst_data.get("minSz", 1))
        
        # Effective Margin (minus fee buffer 0.06%) -> Total Position Value -> Number of Contracts
        fee_buffer = 0.0006
        effective_margin = margin_amount * (1 - fee_buffer)
        position_value = effective_margin * leverage
        
        # Number of contracts = Position Value / (Price * Contract Value)
        # e.g. 1000 USDT / (0.2 * 1) = 5000 contracts
        num_contracts = position_value / (last_price * ct_val)
        
        # Round to integer (OKX contracts are usually integers)
        sz = int(num_contracts)
        
        if sz < min_sz:
            return {"status": "failed", "error": f"Calculated contracts {sz} < minSz {min_sz}"}

        print(f"[EXECUTOR] Placing Futures {side.upper()} {symbol}: {sz} contracts ({leverage}x)")
        
        result = self.okx.place_futures_order(
            instId=symbol,
            side=order_side,
            ordType="market",
            sz=str(sz),
            posSide=pos_side,
            lever=str(leverage),
            slTriggerPx=str(stop_loss) if stop_loss else None,
            tpTriggerPx=str(take_profit) if take_profit else None
        )

        if result.get("code") == "0":
            return {"status": "success", "details": result}
        else:
            return {"status": "failed", "error": result.get("msg")}

# Helper for CLI
def find_latest_analysis_file(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files: files = glob.glob(os.path.join("..", pattern))
    return max(files, key=os.path.getctime) if files else None

def main():
    parser = argparse.ArgumentParser(description="Trade Executor CLI")
    parser.add_argument("--symbol", type=str, required=True)
    parser.add_argument("--side", type=str, required=True, help="buy/sell/long/short")
    parser.add_argument("--amount", type=float, required=True, help="Amount in USDT")
    parser.add_argument("--type", type=str, default="spot", help="spot/futures")
    parser.add_argument("--leverage", type=int, default=1)
    
    args = parser.parse_args()
    
    executor = TradeExecutor()
    if args.type == "spot":
        print(executor.execute_spot(args.symbol, args.side, args.amount))
    else:
        print(executor.execute_futures(args.symbol, args.side, args.amount, args.leverage))

if __name__ == "__main__":
    main()
