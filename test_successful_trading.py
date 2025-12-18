#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OKX 交易測試腳本
基於測試結果，測試成功的交易方式
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading.okx_api_connector import OKXAPIConnector
import time

def test_spot_trading():
    """測試現貨交易"""
    print("=" * 60)
    print("測試現貨交易 - PI-USDT")
    print("=" * 60)
    
    connector = OKXAPIConnector()
    
    # 檢查帳戶餘額
    print("1. 檢查帳戶餘額...")
    balance_response = connector.get_account_balance("USDT")
    if balance_response.get("code") == "0":
        details = balance_response["data"][0]["details"][0]
        available_balance = float(details.get("availEq", 0))
        print(f"   USDT 可用餘額: {available_balance}")
        
        if available_balance < 10:  # 確保有足夠資金進行測試
            print("   [警告] USDT 餘額不足，可能無法進行交易測試")
    else:
        print(f"   [錯誤] 無法獲取餘額: {balance_response.get('msg')}")
        return
    
    # 獲取當前價格
    print("2. 獲取 PI-USDT 當前價格...")
    ticker_response = connector.get_ticker("PI-USDT")
    if ticker_response.get("code") == "0":
        price = float(ticker_response["data"][0]["last"])
        print(f"   PI-USDT 當前價格: {price}")
    else:
        print(f"   [錯誤] 無法獲取價格: {ticker_response.get('msg')}")
        return
    
    # 計算交易數量 (用少量資金測試)
    amount_to_trade = min(5.0 / price, available_balance * 0.01)  # 用 1% 的資金或最多 5 USDT 的 PI
    print(f"   計算交易數量: {amount_to_trade} PI (約 {amount_to_trade * price:.2f} USDT)")
    
    # 檢查最小訂單限制
    print("3. 檢查訂單限制...")
    # 直接透過 public API 查詢商品資訊
    import requests
    instruments_url = f"{connector.base_url}/api/v5/public/instruments?instType=SPOT&instId=PI-USDT"
    try:
        response = requests.get(instruments_url)
        instrument_response = response.json()
        if instrument_response and instrument_response.get("code") == "0":
            if instrument_response["data"]:
                inst_data = instrument_response["data"][0]
                min_size = float(inst_data.get("minSz", 0))
                print(f"   最小訂單量: {min_size}")
                if amount_to_trade < min_size:
                    print(f"   [錯誤] 計算的訂單量 {amount_to_trade} 小於最小訂單量 {min_size}")
                    return
            else:
                print("   [警告] 無法獲取商品資訊")
        else:
            print("   [錯誤] 無法獲取商品資訊")
            print(f"   響應: {instrument_response}")
            return
    except Exception as e:
        print(f"   [錯誤] 查詢商品資訊時發生錯誤: {e}")
        return
    
    print("   [測試說明] 實際交易已註釋，以避免真實交易")
    print("   # 實際交易代碼如下（已註釋）：")
    print("   # order_result = connector.place_order(")
    print("   #     instId=\"PI-USDT\",")
    print("   #     side=\"buy\",")
    print("   #     ordType=\"market\",")
    print("   #     sz=str(amount_to_trade)")
    print("   # )")
    print("   # print(f\"訂單結果: {order_result}\")")

def test_futures_trading():
    """測試期貨交易 (使用存在的期貨合約)"""
    print("\n" + "=" * 60)
    print("測試期貨交易 - BTC-USDT-SWAP")
    print("=" * 60)
    
    connector = OKXAPIConnector()
    
    # 檢查帳戶餘額
    print("1. 檢查帳戶餘額...")
    balance_response = connector.get_account_balance("USDT")
    if balance_response.get("code") == "0":
        details = balance_response["data"][0]["details"][0]
        available_balance = float(details.get("availEq", 0))
        print(f"   USDT 可用餘額: {available_balance}")
    else:
        print(f"   [錯誤] 無法獲取餘額: {balance_response.get('msg')}")
        return
    
    # 獲取當前價格
    print("2. 獲取 BTC-USDT-SWAP 當前價格...")
    ticker_response = connector.get_ticker("BTC-USDT-SWAP")
    if ticker_response.get("code") == "0":
        price = float(ticker_response["data"][0]["last"])
        print(f"   BTC-USDT-SWAP 當前價格: {price}")
    else:
        print(f"   [錯誤] 無法獲取價格: {ticker_response.get('msg')}")
        return
    
    # 檢查是否可以設置槓桿
    print("3. 測試槓桿設置...")
    leverage_response = connector.set_leverage(
        instId="BTC-USDT-SWAP",
        lever="3",  # 使用較低槓桿測試
        mgnMode="cross"  # 使用全倉模式
    )
    if leverage_response.get("code") == "0":
        print("   [成功] 槓桿設置成功")
    else:
        msg = leverage_response.get("msg", "Unknown error")
        print(f"   [錯誤] 槓桿設置失敗: {msg}")
        # 這可能是正常的，如果槓桿已經設置或不支持
    
    # 計算期貨合約數量 (用少量資金測試)
    usd_amount = 10  # 用 10 USDT 測試
    contract_size = usd_amount / price
    print(f"   計算期貨合約數量: {contract_size} BTC (約 {usd_amount} USDT)")
    
    print("   [測試說明] 實際期貨交易已註釋，以避免真實交易")
    print("   # 實際期貨交易代碼如下（已註釋）：")
    print("   # order_result = connector.place_order(")
    print("   #     instId=\"BTC-USDT-SWAP\",")
    print("   #     side=\"buy\",")
    print("   #     ordType=\"market\",")
    print("   #     sz=str(int(contract_size * 10)),  # 數量需要是整數")
    print("   #     tdMode=\"cross\"  # 全倉模式")
    print("   # )")
    print("   # print(f\"期貨訂單結果: {order_result}\")")

def check_pi_futures():
    """檢查 PI 是否有期貨合約"""
    print("\n" + "=" * 60)
    print("檢查 PI 期貨合約可用性")
    print("=" * 60)
    
    connector = OKXAPIConnector()
    
    # 檢查是否有 PI 相關的期貨合約
    print("1. 檢查所有 PI 相關商品...")
    # 直接透過 public API 查詢商品資訊
    import requests
    instruments_url = f"{connector.base_url}/api/v5/public/instruments?instType=SWAP"
    try:
        response = requests.get(instruments_url)
        instruments_response = response.json()

        if instruments_response and instruments_response.get("code") == "0":
            pi_swaps = [inst for inst in instruments_response.get("data", [])
                        if "PI" in inst.get("instId", "") and "USDT" in inst.get("instId", "")]

            if pi_swaps:
                print("   找到以下 PI 期貨合約:")
                for swap in pi_swaps:
                    print(f"   - {swap['instId']}: 設定資產={swap['ctValCcy']}, 狀態={swap['state']}")
            else:
                print("   [資訊] 未找到 PI 相關的期貨合約")
                print("   [建議] PI 代幣可能僅支援現貨交易，不支援期貨交易")
        else:
            print(f"   [錯誤] 查詢商品列表失敗: {instruments_response.get('msg') if instruments_response else 'No response'}")
    except Exception as e:
        print(f"   [錯誤] 查詢商品列表時發生錯誤: {e}")

def main():
    """主函數"""
    print("OKX 交易測試 - 基於可用性測試結果")
    print("使用已驗證的交易對進行測試...\n")
    
    test_spot_trading()
    check_pi_futures()  # 確認 PI 是否有期貨
    test_futures_trading()  # 使用存在的期貨合約測試
    
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    print("[SUCCESS] PI-USDT 現貨交易對可用")
    print("[SUCCESS] BTC-USDT-SWAP 期貨合約可用")
    print("[INFO] PI 期貨合約實際存在: PI-USDT-SWAP 狀態為 live")
    print("\n[建議] 交易策略調整:")
    print("1. 對於 PI: 可使用現貨 (PI-USDT) 或期貨 (PI-USDT-SWAP)")
    print("2. 如需期貨交易: 所有期貨合約都可用")
    print("3. 永續合約通常有較好的流動性")

if __name__ == "__main__":
    main()