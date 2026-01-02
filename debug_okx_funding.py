import os
import asyncio
from dotenv import load_dotenv
from trading.okx_api_connector import OKXAPIConnector
import json

load_dotenv(override=True)

def debug_funding():
    api = OKXAPIConnector()
    
    # 1. Check Instruments (for Max/Min limits)
    print("--- Fetching Instruments (SWAP) ---")
    instruments = api.get_instruments("SWAP")
    if instruments.get("code") == "0":
        data = instruments.get("data", [])
        print(f"Total SWAP instruments: {len(data)}")
        # Print first USDT swap details to check keys
        for inst in data:
            if inst['instId'].endswith('-USDT-SWAP'):
                print(f"Sample Instrument ({inst['instId']}):")
                print(json.dumps(inst, indent=2))
                break
    else:
        print(f"Error fetching instruments: {instruments}")

    # 2. Check Funding Rate (for one symbol)
    print("\n--- Fetching Funding Rate (BTC-USDT-SWAP) ---")
    fr = api.get_funding_rate("BTC-USDT-SWAP")
    print(json.dumps(fr, indent=2))

if __name__ == "__main__":
    debug_funding()
