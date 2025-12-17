#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick test to run PIUSDT with the updated batch analyzer
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from analysis.batch_analyzer import run_full_analysis

async def test_single_symbol():
    print("Testing individual PIUSDT symbol analysis...")
    
    # Test just PIUSDT
    results = await run_full_analysis(
        exchange_name="okx", 
        market_type="spot", 
        custom_symbols=["PIUSDT"],
        include_account_balance=False
    )
    
    print(f"Results: {results}")
    
    if results:
        for result in results:
            print(f"Symbol: {result.get('symbol')}")
            print(f"Signal: {result.get('signal')}")
            print(f"Reasoning: {result.get('reasoning', 'N/A')}")
            print("-" * 50)
    else:
        print("No results returned.")

if __name__ == "__main__":
    asyncio.run(test_single_symbol())