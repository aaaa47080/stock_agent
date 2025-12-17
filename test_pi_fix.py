#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify the PIUSDT symbol fix
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from analysis.batch_analyzer import convert_symbol_format

async def test_pi_conversion():
    print("Testing PIUSDT symbol conversion...")
    
    # Test the conversion function
    original_symbol = "PIUSDT"
    converted_to_okx = convert_symbol_format(original_symbol, "binance", "okx")
    print(f"Converting '{original_symbol}' from binance to okx: {converted_to_okx}")
    
    # Test the conversion in the opposite direction
    converted_to_binance = convert_symbol_format(converted_to_okx, "okx", "binance")
    print(f"Converting '{converted_to_okx}' from okx to binance: {converted_to_binance}")
    
    # Test with other symbols too
    symbols_to_test = ["PIUSDT", "ETHUSDT", "BTCUSDT"]
    for symbol in symbols_to_test:
        converted = convert_symbol_format(symbol, "binance", "okx")
        print(f"Convert '{symbol}' from binance to okx: {converted}")

if __name__ == "__main__":
    asyncio.run(test_pi_conversion())