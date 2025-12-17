#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple test to check if PIUSDT symbol exists on OKX
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_fetcher import get_data_fetcher, SymbolNotFoundError

def test_pi_symbol():
    print("Testing PIUSDT symbol on OKX...")

    # Get OKX data fetcher
    okx_fetcher = get_data_fetcher("okx")

    # Test the symbol in different formats
    symbols_to_test = [
        "PI-USDT",  # Standard format
        "PIUSDT",   # Alternative format
    ]

    for symbol in symbols_to_test:
        print(f"\nTesting symbol: {symbol}")
        try:
            # First, check if the symbol exists
            okx_fetcher.check_symbol_availability(symbol, inst_type='SPOT')
            print(f"[SUCCESS] Symbol {symbol} exists on OKX SPOT market!")

            # Try to get some historical data
            df = okx_fetcher.get_historical_klines(symbol, '1d', limit=5)
            if df is not None and not df.empty:
                print(f"[SUCCESS] Successfully retrieved data for {symbol}")
                print(f"  Last close price: {df.iloc[-1]['Close']}")
                print(f"  Data range: {df.iloc[0]['Open_time']} to {df.iloc[-1]['Open_time']}")
            else:
                print(f"[ERROR] Could not retrieve data for {symbol}, but the symbol exists")

        except SymbolNotFoundError as e:
            print(f"[ERROR] Symbol {symbol} not found on OKX: {e}")
        except Exception as e:
            print(f"[ERROR] Error testing {symbol}: {e}")

    print("\n" + "="*50)
    print("Getting top symbols from OKX for comparison:")
    try:
        top_symbols = okx_fetcher.get_top_symbols(limit=20)
        print("Top 20 symbols on OKX:")
        for i, symbol in enumerate(top_symbols, 1):
            print(f"  {i:2d}. {symbol}")
    except Exception as e:
        print(f"[ERROR] Error getting top symbols: {e}")

if __name__ == "__main__":
    test_pi_symbol()