"""演示不同的交易配置場景"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def demo_scenarios():
    """演示不同配置場景的輸出"""
    print("="*70)
    print("交易類型配置 - 場景演示")
    print("="*70)

    # 模擬交易決策
    sample_decision = {
        "symbol": "PI-USDT",
        "spot_decision": {
            "should_trade": True,
            "market_type": "spot",
            "symbol_for_trade": "PI-USDT",
            "action": "buy",
            "investment_amount_usdt": 25,
            "reasoning": "技術指標顯示上漲趨勢"
        },
        "futures_decision": {
            "should_trade": True,
            "market_type": "futures",
            "symbol_for_trade": "PI-USDT",
            "action": "long",
            "investment_amount_usdt": 25,
            "leverage": 10,
            "reasoning": "強勁的動能和成交量支持"
        }
    }

    print("\n假設系統生成了以下交易決策:")
    print("-" * 70)
    print("現貨決策: BUY PI-USDT with $25")
    print("合約決策: LONG PI-USDT-SWAP with $25 (10x leverage)")
    print("-" * 70)

    scenarios = [
        {
            "name": "場景 1: 兩種交易都執行 (預設)",
            "spot": True,
            "futures": True,
            "description": "現貨和合約交易都會被執行"
        },
        {
            "name": "場景 2: 只執行現貨交易",
            "spot": True,
            "futures": False,
            "description": "只執行現貨買入，跳過合約交易"
        },
        {
            "name": "場景 3: 只執行合約交易",
            "spot": False,
            "futures": True,
            "description": "跳過現貨交易，只執行合約做多"
        },
        {
            "name": "場景 4: 不執行任何交易",
            "spot": False,
            "futures": False,
            "description": "只生成分析報告，不實際下單"
        }
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*70}")
        print(f"{scenario['name']}")
        print(f"{'='*70}")
        print(f"配置: ENABLE_SPOT_TRADING = {scenario['spot']}")
        print(f"      ENABLE_FUTURES_TRADING = {scenario['futures']}")
        print(f"\n說明: {scenario['description']}")
        print(f"\n預期行為:")

        if scenario['spot'] and scenario['futures']:
            print("  [YES] 執行現貨買入 PI-USDT")
            print("  [YES] 執行合約做多 PI-USDT-SWAP")
        elif scenario['spot'] and not scenario['futures']:
            print("  [YES] 執行現貨買入 PI-USDT")
            print("  [NO]  跳過合約交易 (已停用)")
        elif not scenario['spot'] and scenario['futures']:
            print("  [NO]  跳過現貨交易 (已停用)")
            print("  [YES] 執行合約做多 PI-USDT-SWAP")
        else:
            print("  [NO]  跳過現貨交易 (已停用)")
            print("  [NO]  跳過合約交易 (已停用)")
            print("  [INFO] 只生成分析報告")

    print(f"\n{'='*70}")
    print("如何修改配置")
    print(f"{'='*70}")
    print("\n在 core/config.py 文件中找到以下行:")
    print("""
    # === 交易類型選擇 ===
    ENABLE_SPOT_TRADING = True      # 改為 False 停用現貨交易
    ENABLE_FUTURES_TRADING = True   # 改為 False 停用合約交易
    """)
    print("\n根據您的需求修改 True/False 值即可。")
    print("="*70)

if __name__ == "__main__":
    demo_scenarios()
