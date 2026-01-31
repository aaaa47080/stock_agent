
import sys
import os
sys.path.insert(0, os.getcwd())

import time
import pandas as pd
from analysis.crypto_screener_light import screen_top_cryptos_light

def test_screener():
    print("Testing screen_top_cryptos_light...")
    start = time.time()
    try:
        df, top, oversold, overbought = screen_top_cryptos_light(exchange='okx', limit=5)
        elapsed = time.time() - start
        print(f"✅ Success! Time: {elapsed:.4f}s")
        
        if not df.empty:
             print("columns:", df.columns.tolist())
             print("First row:", df.iloc[0].to_dict())
        else:
             print("⚠️ DataFrame is empty")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_screener()
