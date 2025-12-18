#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OKX 合約可用性測試腳本
用於測試哪些合約在 OKX 上可用，以及正確的交易方式
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json
from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
from trading.okx_api_connector import OKXAPIConnector

def test_spot_availability():
    """測試現貨交易對可用性"""
    print("=" * 60)
    print("測試現貨交易對可用性")
    print("=" * 60)
    
    okx_fetcher = get_data_fetcher("okx")
    
    # 測試 PI 相關交易對
    spot_symbols = [
        "PI-USDT",    # 轉換後的格式
        "PIUSDT",     # 原始格式
    ]
    
    for symbol in spot_symbols:
        print(f"\n測試現貨交易對: {symbol}")
        try:
            okx_fetcher.check_symbol_availability(symbol, inst_type='SPOT')
            print(f"[SUCCESS] {symbol} 現貨交易對存在")

            # 獲取一些歷史數據驗證
            df = okx_fetcher.get_historical_klines(symbol, '1d', limit=5)
            if df is not None and not df.empty:
                print(f"  - 成功獲取數據，當前價格: {df.iloc[-1]['Close']}")
            else:
                print(f"  - 無法獲取數據")
        except SymbolNotFoundError as e:
            print(f"[ERROR] {symbol} 現貨交易對不存在: {e}")
        except Exception as e:
            print(f"[ERROR] {symbol} 測試出錯: {e}")

def test_futures_availability():
    """測試期貨合約可用性"""
    print("\n" + "=" * 60)
    print("測試期貨合約可用性")
    print("=" * 60)
    
    okx_fetcher = get_data_fetcher("okx")
    
    # 測試 PI 相關期貨合約
    futures_symbols = [
        "PI-USDT-SWAP",  # 永續合約格式
        "PIUSDT-SWAP",   # 原始格式轉換
    ]
    
    for symbol in futures_symbols:
        print(f"\n測試期貨合約: {symbol}")
        try:
            # 直接調用 API 檢查合約是否存在
            connector = OKXAPIConnector()
            result = connector.get_instrument_details(symbol)
            if result.get("code") == "0" and len(result.get("data", [])) > 0:
                print(f"[SUCCESS] {symbol} 期貨合約存在")
                instrument_data = result["data"][0]
                print(f"  - 狀態: {instrument_data.get('state', 'N/A')}")
                print(f"  - 標的資產: {instrument_data.get('ctVal', 'N/A')}")
                print(f"  - 標的幣種: {instrument_data.get('ctValCcy', 'N/A')}")
            else:
                print(f"[ERROR] {symbol} 期貨合約不存在或已下線")
        except Exception as e:
            print(f"[ERROR] {symbol} 測試出錯: {e}")

    # 測試其他常見的期貨合約以確認 API 是否正常
    print(f"\n測試其他常見期貨合約 (用於對比):")
    common_futures = [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
    ]

    for symbol in common_futures:
        print(f"\n測試期貨合約: {symbol}")
        try:
            # 直接調用 API 檢查合約是否存在
            connector = OKXAPIConnector()
            result = connector.get_instrument_details(symbol)
            if result.get("code") == "0" and len(result.get("data", [])) > 0:
                print(f"[SUCCESS] {symbol} 期貨合約存在")
                instrument_data = result["data"][0]
                print(f"  - 狀態: {instrument_data.get('state', 'N/A')}")
            else:
                print(f"[ERROR] {symbol} 期貨合約不存在或已下線")
        except Exception as e:
            print(f"[ERROR] {symbol} 測試出錯: {e}")

def test_account_balance():
    """測試帳戶餘額功能"""
    print("\n" + "=" * 60)
    print("測試帳戶餘額功能")
    print("=" * 60)
    
    try:
        connector = OKXAPIConnector()
        balance_response = connector.get_account_balance("USDT")
        
        if balance_response.get("code") == "0":
            balance_data = balance_response.get("data", [])
            if balance_data and len(balance_data) > 0:
                details = balance_data[0].get("details", [])
                if details:
                    usdt_balance = details[0]
                    available_balance = float(usdt_balance.get("availEq", 0))
                    total_balance = float(usdt_balance.get("eq", 0))
                    print(f"[SUCCESS] 帳戶餘額查詢成功")
                    print(f"  - 總餘額: ${total_balance}")
                    print(f"  - 可用餘額: ${available_balance}")
                else:
                    print("[ERROR] 無法獲取 USDT 餘額明細")
            else:
                print("[ERROR] 無法獲取帳戶餘額資料")
        else:
            print(f"[ERROR] 帳戶餘額查詢失敗: {balance_response.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"[ERROR] 帳戶餘額查詢出錯: {e}")

def test_market_ticker():
    """測試市場行情功能"""
    print("\n" + "=" * 60)
    print("測試市場行情功能")
    print("=" * 60)
    
    available_pairs = [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
        "PI-USDT",  # 現貨
    ]
    
    connector = OKXAPIConnector()
    
    for pair in available_pairs:
        print(f"\n測試行情: {pair}")
        try:
            ticker_response = connector.get_ticker(pair)
            if ticker_response.get("code") == "0" and len(ticker_response.get("data", [])) > 0:
                ticker_data = ticker_response["data"][0]
                last_price = ticker_data.get("last", "N/A")
                print(f"[SUCCESS] {pair} 行情獲取成功")
                print(f"  - 最新價格: {last_price}")
                print(f"  - 24H 最高: {ticker_data.get('high24h', 'N/A')}")
                print(f"  - 24H 最低: {ticker_data.get('low24h', 'N/A')}")
            else:
                print(f"[ERROR] {pair} 行情獲取失敗: {ticker_response.get('msg', 'No data')}")
        except Exception as e:
            print(f"[ERROR] {pair} 行情獲取出錯: {e}")

def main():
    """主函數"""
    print("OKX 交易合約可用性測試")
    print("開始測試各項功能...")
    
    test_spot_availability()
    test_futures_availability()
    test_account_balance()
    test_market_ticker()
    
    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)
    print("\n根據測試結果，您可以：")
    print("1. 確認哪些交易對可用於現貨交易")
    print("2. 確認哪些期貨合約存在")
    print("3. 驗證帳戶連接是否正常")
    print("4. 測試市場數據獲取功能")

if __name__ == "__main__":
    main()