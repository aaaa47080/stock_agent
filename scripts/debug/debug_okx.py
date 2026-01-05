import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from data.data_fetcher import get_data_fetcher
import json

def test_okx_symbols():
    try:
        print("Initializing OKX Fetcher...")
        fetcher = get_data_fetcher("okx")
        print(f"Base URL: {fetcher.base_url}")
        
        print("Fetching all symbols...")
        symbols = fetcher.get_all_symbols()
        print(f"Found {len(symbols)} symbols.")
        if symbols:
            print(f"First 10: {symbols[:10]}")
        else:
            print("No symbols returned. Checking raw request...")
            # Try to see what's happening
            endpoint = "/public/instruments"
            params = {'instType': 'SPOT'}
            data = fetcher._make_request(endpoint, params)
            if data is None:
                print("Raw request returned None.")
            else:
                print(f"Raw data length: {len(data)}")
                if len(data) > 0:
                    print(f"Sample item keys: {data[0].keys()}")
                    print(f"Sample item instId: {data[0].get('instId')}, state: {data[0].get('state')}")
                    
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_okx_symbols()
