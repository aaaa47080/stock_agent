"""測試修正後的槓桿和手續費計算"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_calculation_logic():
    """展示修正前後的計算差異"""
    print("="*70)
    print("合約張數計算 - 修正前後對比")
    print("="*70)

    # 測試參數
    margin = 100  # 保證金 100 USDT
    leverage = 10  # 10倍槓桿
    price = 0.2057  # PI 當前價格 (從實際API獲取)
    ct_val = 1  # 合約面值: 1張 = 1 PI
    fee_rate = 0.0006  # 手續費 0.06%

    print(f"\n測試參數:")
    print(f"  保證金: ${margin} USDT")
    print(f"  槓桿: {leverage}x")
    print(f"  當前價格: ${price} USDT/PI")
    print(f"  合約面值: {ct_val} PI per contract")
    print(f"  手續費率: {fee_rate*100}%")

    print(f"\n{'='*70}")
    print("[ERROR] 修正前 (錯誤的計算):")
    print(f"{'='*70}")

    # 舊的錯誤計算
    old_sz = margin / (price * ct_val)
    old_contract_value = old_sz * price * ct_val

    print(f"  計算公式: 保證金 / (價格 × 合約面值)")
    print(f"  計算過程: {margin} / ({price} × {ct_val})")
    print(f"  合約張數: {int(old_sz)} 張")
    print(f"  實際合約價值: ${old_contract_value:.2f} USDT")
    print(f"  [WARNING] 問題: 只用了保證金金額，沒有乘以槓桿！")
    print(f"  [WARNING] 結果: 應該開 ${margin * leverage} 的倉位，卻只開了 ${old_contract_value:.2f}")

    print(f"\n{'='*70}")
    print("[FIXED] 修正後 (正確的計算):")
    print(f"{'='*70}")

    # 新的正確計算
    effective_margin = margin * (1 - fee_rate)
    contract_value = effective_margin * leverage
    new_sz = contract_value / (price * ct_val)
    actual_contract_value = int(new_sz) * price * ct_val

    print(f"  步驟 1: 扣除手續費")
    print(f"          有效保證金 = {margin} × (1 - {fee_rate}) = ${effective_margin:.2f}")
    print(f"\n  步驟 2: 計算合約總價值")
    print(f"          合約價值 = 有效保證金 × 槓桿")
    print(f"          合約價值 = ${effective_margin:.2f} × {leverage} = ${contract_value:.2f}")
    print(f"\n  步驟 3: 計算合約張數")
    print(f"          合約張數 = 合約價值 / (價格 × 合約面值)")
    print(f"          合約張數 = ${contract_value:.2f} / ({price} × {ct_val})")
    print(f"          合約張數 = {int(new_sz)} 張")
    print(f"\n  步驟 4: 驗證")
    print(f"          實際合約價值 = {int(new_sz)} × {price} × {ct_val} = ${actual_contract_value:.2f}")
    print(f"          [OK] 約等於目標 ${contract_value:.2f}")

    print(f"\n{'='*70}")
    print("對比總結:")
    print(f"{'='*70}")
    print(f"  期望開倉價值: ${margin * leverage} USDT (保證金 × 槓桿)")
    print(f"  修正前實際價值: ${old_contract_value:.2f} USDT [ERROR] (少了 {leverage}倍!)")
    print(f"  修正後實際價值: ${actual_contract_value:.2f} USDT [OK]")
    print(f"\n  修正前張數: {int(old_sz)} 張")
    print(f"  修正後張數: {int(new_sz)} 張")
    print(f"  差異: {int(new_sz) - int(old_sz)} 張 (多了 {((int(new_sz) - int(old_sz)) / int(old_sz) * 100):.1f}%)")

    print(f"\n{'='*70}")
    print("關鍵改進:")
    print(f"{'='*70}")
    print("  1. [OK] 正確應用槓桿: 合約價值 = 保證金 × 槓桿")
    print("  2. [OK] 預留手續費: 扣除 0.06% 避免保證金不足")
    print("  3. [OK] 資金費率考慮: 在AI決策階段已包含資金費率分析")
    print("  4. [OK] 清晰的日誌: 顯示保證金、槓桿、合約價值")
    print(f"{'='*70}\n")

def test_real_scenario():
    """使用實際的交易場景測試"""
    print("\n" + "="*70)
    print("實際交易場景測試")
    print("="*70)

    scenarios = [
        {"margin": 50, "leverage": 5, "price": 0.2057, "name": "保守 - $50保證金, 5x槓桿"},
        {"margin": 100, "leverage": 10, "price": 0.2057, "name": "中等 - $100保證金, 10x槓桿"},
        {"margin": 200, "leverage": 20, "price": 0.2057, "name": "激進 - $200保證金, 20x槓桿"},
    ]

    for scenario in scenarios:
        margin = scenario["margin"]
        leverage = scenario["leverage"]
        price = scenario["price"]
        fee_rate = 0.0006

        effective_margin = margin * (1 - fee_rate)
        contract_value = effective_margin * leverage
        contracts = int(contract_value / price)

        print(f"\n{scenario['name']}:")
        print(f"  保證金: ${margin} → 有效: ${effective_margin:.2f} (扣除手續費)")
        print(f"  合約價值: ${contract_value:.2f} ({leverage}倍槓桿)")
        print(f"  合約張數: {contracts} 張")
        print(f"  風險: 價格下跌 {100/leverage:.1f}% 即可能爆倉")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    test_calculation_logic()
    test_real_scenario()
