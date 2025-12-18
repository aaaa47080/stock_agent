#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試當前後端分析器是否正確生成符號
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.backend_analyzer import BackendAnalyzer

def test_current_conversion():
    """測試當前的符號轉換邏輯"""
    analyzer = BackendAnalyzer()
    
    # 模擬一個包含 PIUSDT 的決策結果
    sample_result = {
        'final_approval': type('obj', (object,), {
            'final_decision': 'Approve',
            'final_position_size': 0.1,
            'approved_leverage': 10,
            'rationale': 'Test rationale'
        })(),
        'trader_decision': type('obj', (object,), {
            'decision': 'Buy',
            'confidence': 80.0,
            'entry_price': 0.205,
            'stop_loss': 0.18,
            'take_profit': 0.25
        })(),
        'exchange': 'okx',
        'current_price': 0.205,
        'risk_assessment': None,
        'bull_argument': None,
        'bear_argument': None,
        'funding_rate_info': {},
        '新聞資訊': {}
    }
    
    print("測試當前後端分析器的符號生成邏輯:")
    print("-" * 50)
    
    # 測試 PIUSDT 符號
    spot_decision = analyzer._extract_decision("PIUSDT", sample_result, 'spot', 
                                              {"available_balance": 500.0})
    futures_decision = analyzer._extract_decision("PIUSDT", sample_result, 'futures', 
                                                 {"available_balance": 500.0})
    
    print(f"輸入符號: PIUSDT")
    print(f"現貨決策符號: {spot_decision['symbol_for_trade']}")
    print(f"期貨決策符號: {futures_decision['symbol_for_trade']}")
    
    print("\n期望結果:")
    print(f"現貨決策符號: PI-USDT (正確)")
    print(f"期貨決策符號: PI-USDT-SWAP (正確)")

if __name__ == "__main__":
    test_current_conversion()