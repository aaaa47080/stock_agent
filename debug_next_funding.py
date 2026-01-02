from trading.okx_api_connector import OKXAPIConnector
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

def check_next_funding():
    api = OKXAPIConnector()
    print("Checking BTC-USDT-SWAP funding rate...")
    
    # 直接呼叫我們剛改過的 function
    all_rates = api.get_all_funding_rates()
    
    if "error" in all_rates:
        print(f"Error getting all rates: {all_rates['error']}")
    elif "BTC-USDT" in all_rates:
        btc_data = all_rates["BTC-USDT"]
        print(json.dumps(btc_data, indent=2))
    else:
        print(f"BTC-USDT not found in cached data. Total keys: {len(all_rates)}")
        
    # 檢查原始數據
    raw_res = api.get_funding_rate("BTC-USDT-SWAP")
    print("\nRaw API Response for BTC-USDT-SWAP:")
    print(json.dumps(raw_res, indent=2))

if __name__ == "__main__":
    check_next_funding()
