#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試後端分析器的符號轉換邏輯
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.backend_analyzer import BackendAnalyzer

def test_symbol_conversion():
    """測試符號轉換邏輯"""
    analyzer = BackendAnalyzer()
    
    # 測試不同的輸入格式
    test_cases = [
        "PIUSDT",
        "BTCUSDT", 
        "ETHUSDT",
        "PI-USDT",  # OKX 已格式化的格式
        "BTC-USDT",
        "PI-USDT-SWAP",  # 期貨格式
    ]
    
    print("測試符號轉換邏輯:")
    print("-" * 60)
    
    for symbol in test_cases:
        # 測試現貨決策的符號格式
        spot_result = analyzer._extract_decision(symbol, None, 'spot', None)
        print(f"輸入: {symbol:<15} -> 現貨符號: {spot_result['symbol_for_trade']:<20}")
        
        # 測試期貨決策的符號格式
        futures_result = analyzer._extract_decision(symbol, None, 'futures', None)
        print(f"{'':<20} -> 期貨符號: {futures_result['symbol_for_trade']:<20}")
        print()

if __name__ == "__main__":
    test_symbol_conversion()