
import sys
import os
import asyncio
import pandas as pd
from pprint import pprint

# Setup path
sys.path.append(os.getcwd())

try:
    from analysis.crypto_screener_light import screen_top_cryptos_light
except ImportError as e:
    print(f"❌ ImportError: {e}")
    sys.exit(1)

def test_screener():
    print("🚀 Testing screen_top_cryptos_light...")
    try:
        # Simulate API call: exchange='okx', limit=10
        df_vol, df_gain, df_loss, _ = screen_top_cryptos_light(exchange='okx', limit=10)
        
        print("\n✅ Execution Successful!")
        print(f"Volume List Size: {len(df_vol)}")
        print(f"Gainers List Size: {len(df_gain)}")
        print(f"Losers List Size: {len(df_loss)}")
        
        if not df_vol.empty:
            print("\n--- Top Volume (First 3) ---")
            print(df_vol[['Symbol', 'Volume', 'price_change_24h']].head(3))
            
        if not df_gain.empty:
            print("\n--- Top Gainers (First 3) ---")
            print(df_gain[['Symbol', 'Volume', 'price_change_24h']].head(3))
            
        if not df_loss.empty:
            print("\n--- Top Losers (First 3) ---")
            print(df_loss[['Symbol', 'Volume', 'price_change_24h']].head(3))

    except Exception as e:
        print(f"\n❌ Runtime Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_screener()
