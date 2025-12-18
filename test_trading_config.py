"""測試交易類型配置選項"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading.okx_auto_trader import execute_trades_from_decision_data

def test_trading_config():
    """測試不同的交易類型配置"""
    print("="*60)
    print("測試交易類型配置選項")
    print("="*60)

    # 模擬的交易決策數據
    test_decisions = [
        {
            "symbol": "PI-USDT",
            "spot_decision": {
                "should_trade": True,
                "market_type": "spot",
                "symbol_for_trade": "PI-USDT",
                "action": "buy",
                "investment_amount_usdt": 25,
                "reasoning": "測試現貨交易決策"
            },
            "futures_decision": {
                "should_trade": True,
                "market_type": "futures",
                "symbol_for_trade": "PI-USDT",
                "action": "long",
                "investment_amount_usdt": 25,
                "leverage": 10,
                "reasoning": "測試合約交易決策"
            }
        }
    ]

    print("\n[INFO] 當前配置:")
    from core.config import ENABLE_SPOT_TRADING, ENABLE_FUTURES_TRADING
    print(f"  ENABLE_SPOT_TRADING = {ENABLE_SPOT_TRADING}")
    print(f"  ENABLE_FUTURES_TRADING = {ENABLE_FUTURES_TRADING}")

    print("\n[INFO] 測試交易決策處理 (模擬模式)...")
    print("="*60)

    # 使用 live_trading=False 進行模擬測試
    execute_trades_from_decision_data(test_decisions, live_trading=False)

    print("\n" + "="*60)
    print("[INFO] 測試完成!")
    print("\n提示:")
    print("  - 要停用現貨交易: 在 core/config.py 中設置 ENABLE_SPOT_TRADING = False")
    print("  - 要停用合約交易: 在 core/config.py 中設置 ENABLE_FUTURES_TRADING = False")
    print("  - 兩者都可以獨立控制，提供最大彈性")
    print("="*60)

if __name__ == "__main__":
    test_trading_config()
