
import sys
import os
import json
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis.crypto_screener import screen_top_cryptos

def test_screener():
    print("Testing Screener...")
    try:
        # Run with a few symbols to be fast
        summary_df, top_performers, oversold, overbought = screen_top_cryptos(
            exchange='okx', 
            limit=5, 
            interval='1d',
            target_symbols=['BTC', 'ETH', 'SOL', 'XRP']
        )
        
        print("\n=== Oversold DataFrame ===")
        if not oversold.empty:
            print(oversold[['Symbol', 'RSI_14', 'Current Price']].to_string())
        else:
            print("Oversold is empty.")

        print("\n=== Summary DataFrame Sample ===")
        print(summary_df[['Symbol', 'RSI_14']].head().to_string())

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_screener()
