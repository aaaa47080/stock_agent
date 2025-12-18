#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試後端分析器的符號格式轉換是否正確
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
        "PI",
        "BTC"
    ]
    
    print("測試符號轉換邏輯:")
    print("-" * 40)
    
    for symbol in test_cases:
        # 測試現貨決策的符號格式
        spot_result = analyzer._extract_decision(symbol, None, 'spot', None)
        print(f"輸入: {symbol:8} -> 現貨符號: {spot_result['symbol_for_trade']:15}")
        
        # 測試期貨決策的符號格式
        futures_result = analyzer._extract_decision(symbol, None, 'futures', None)
        print(f"              -> 期貨符號: {futures_result['symbol_for_trade']:15}")
        print()

if __name__ == "__main__":
    test_symbol_conversion()