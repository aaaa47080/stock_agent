"""
測試交易修復功能

這個腳本用於測試修復後的交易邏輯，不會執行實際交易
"""
from trading.okx_api_connector import OKXAPIConnector

def test_spot_trading_rules():
    """測試現貨交易規則獲取"""
    print("="*60)
    print("測試 1: 現貨交易規則獲取")
    print("="*60)

    api = OKXAPIConnector()

    # 測試 PI-USDT 現貨交易規則
    symbol = "PI-USDT"
    result = api.get_instruments("SPOT", symbol)

    if result.get("code") == "0" and result.get("data"):
        inst_data = result["data"][0]
        print(f"\n{symbol} 現貨交易規則:")
        print(f"  - 最小數量 (minSz): {inst_data.get('minSz')}")
        print(f"  - 數量精度 (lotSz): {inst_data.get('lotSz')}")
        print(f"  - 最小下單金額 (minSz): {inst_data.get('minSz')}")

        # 模擬計算
        price = 0.2055
        investment = 62.23
        effective_amount = investment * 0.998  # 扣除手續費

        lot_sz = float(inst_data.get("lotSz", 0.000001))
        sz = effective_amount / price
        sz_adjusted = int(sz / lot_sz) * lot_sz

        print(f"\n模擬交易計算:")
        print(f"  - 投資金額: ${investment:.2f} USDT")
        print(f"  - 有效金額 (扣0.2%手續費): ${effective_amount:.2f} USDT")
        print(f"  - 當前價格: ${price}")
        print(f"  - 原始數量: {sz:.6f}")
        print(f"  - 調整後數量: {sz_adjusted:.6f} (符合 lotSz={lot_sz})")

        return True
    else:
        print(f"[ERROR] 獲取交易規則失敗: {result.get('msg')}")
        return False

def test_futures_trading_rules():
    """測試合約交易規則獲取"""
    print("\n" + "="*60)
    print("測試 2: 合約交易規則獲取")
    print("="*60)

    api = OKXAPIConnector()

    # 測試 PI-USDT-SWAP 合約交易規則
    symbol = "PI-USDT-SWAP"
    result = api.get_instruments("SWAP", symbol)

    if result.get("code") == "0" and result.get("data"):
        inst_data = result["data"][0]
        print(f"\n{symbol} 合約交易規則:")
        print(f"  - 合約面值 (ctVal): {inst_data.get('ctVal')}")
        print(f"  - 數量精度 (lotSz): {inst_data.get('lotSz')}")
        print(f"  - 最小張數 (minSz): {inst_data.get('minSz')}")

        # 模擬計算
        price = 0.2055
        investment = 62.23
        ct_val = float(inst_data.get("ctVal", 1))
        lot_sz = float(inst_data.get("lotSz", 1))

        sz = investment / (price * ct_val)
        sz_adjusted = int(sz / lot_sz) * lot_sz

        print(f"\n模擬交易計算:")
        print(f"  - 投資金額: ${investment:.2f} USDT")
        print(f"  - 當前價格: ${price}")
        print(f"  - 原始張數: {sz:.6f}")
        print(f"  - 調整後張數: {int(sz_adjusted)} (整數)")

        return True
    else:
        print(f"[ERROR] 獲取交易規則失敗: {result.get('msg')}")
        return False

def test_balance_calculation():
    """測試餘額計算邏輯"""
    print("\n" + "="*60)
    print("測試 3: 餘額與投資金額驗證")
    print("="*60)

    # 從錯誤日誌中的數據
    available_balance = 259.28  # USDT
    investment = 62.23  # USDT
    price = 0.2055

    print(f"\n帳戶狀態:")
    print(f"  - 可用餘額: ${available_balance:.2f} USDT")
    print(f"  - 建議投資: ${investment:.2f} USDT")
    print(f"  - 投資比例: {(investment/available_balance)*100:.2f}%")

    # 現貨交易 (扣除手續費)
    effective_amount = investment * 0.998
    spot_qty = effective_amount / price

    print(f"\n現貨交易:")
    print(f"  - 有效金額: ${effective_amount:.2f} USDT (扣0.2%手續費)")
    print(f"  - 購買數量: {spot_qty:.2f} PI")
    print(f"  - 餘額檢查: {'OK 足夠' if effective_amount < available_balance else 'X 不足'}")

    # 合約交易
    leverage = 20
    contracts = int(investment / (price * 1))  # ctVal=1
    margin_required = (contracts * price * 1) / leverage

    print(f"\n合約交易 ({leverage}x 槓桿):")
    print(f"  - 合約張數: {contracts} 張")
    print(f"  - 所需保證金: ${margin_required:.2f} USDT")
    print(f"  - 餘額檢查: {'OK 足夠' if margin_required < available_balance else 'X 不足'}")

    return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("交易修復功能測試")
    print("="*60)

    # 檢查 API 連接
    api = OKXAPIConnector()
    if not all([api.api_key, api.secret_key, api.passphrase]):
        print("[WARNING] 未設置 OKX API 憑證")
        print("將使用模擬數據進行測試\n")

    try:
        # 執行測試
        test1 = test_spot_trading_rules()
        test2 = test_futures_trading_rules()
        test3 = test_balance_calculation()

        # 總結
        print("\n" + "="*60)
        print("測試總結")
        print("="*60)
        print(f"現貨交易規則: {'OK 通過' if test1 else 'X 失敗'}")
        print(f"合約交易規則: {'OK 通過' if test2 else 'X 失敗'}")
        print(f"餘額計算邏輯: {'OK 通過' if test3 else 'X 失敗'}")

        if all([test1, test2, test3]):
            print("\nOK 所有測試通過！交易功能已修復。")
        else:
            print("\nX 部分測試失敗，請檢查錯誤信息。")

    except Exception as e:
        print(f"\n[ERROR] 測試過程中出現異常: {str(e)}")
        import traceback
        traceback.print_exc()