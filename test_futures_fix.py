"""測試修復後的期貨交易功能"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading.okx_api_connector import OKXAPIConnector
from trading.okx_auto_trader import execute_futures_trade

def test_futures_order():
    """測試期貨下單是否正確處理持倉模式"""
    print("="*60)
    print("測試期貨交易 - 持倉模式修復")
    print("="*60)

    okx_api = OKXAPIConnector()

    if not all([okx_api.api_key, okx_api.secret_key, okx_api.passphrase]):
        print("[ERROR] OKX API credentials are not set.")
        return

    # 測試交易決策數據 (小額測試)
    test_trade_decision = {
        "market_type": "futures",
        "symbol_for_trade": "PI-USDT",  # 將自動轉換為 PI-USDT-SWAP
        "action": "long",  # 做多
        "investment_amount_usdt": 26,  # 小額測試
        "leverage": 10,
        "reasoning": "測試單 - 驗證持倉模式修復"
    }

    print("\n[TEST] 模擬交易決策:")
    print(f"  Symbol: {test_trade_decision['symbol_for_trade']}")
    print(f"  Action: {test_trade_decision['action']}")
    print(f"  Amount: ${test_trade_decision['investment_amount_usdt']}")
    print(f"  Leverage: {test_trade_decision['leverage']}x")

    print("\n[INFO] 執行期貨交易...")
    print("="*60)

    # 執行交易
    execute_futures_trade(
        okx_api=okx_api,
        symbol=test_trade_decision["symbol_for_trade"],
        action=test_trade_decision["action"],
        trade_data=test_trade_decision
    )

    print("\n" + "="*60)
    print("[TEST] 測試完成")
    print("="*60)

if __name__ == "__main__":
    test_futures_order()
