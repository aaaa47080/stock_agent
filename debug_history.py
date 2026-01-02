from trading.okx_api_connector import OKXAPIConnector
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

def debug_history():
    api = OKXAPIConnector()
    symbol = "BTC-USDT-SWAP"
    print(f"Testing history fetch for {symbol}...")
    
    # 直接呼叫 connector 的方法
    res = api.get_funding_rate_history(symbol, limit=5)
    
    print("\nAPI Response:")
    print(json.dumps(res, indent=2))
    
    if res.get("code") == "0" and res.get("data"):
        print(f"\nSuccess! Got {len(res['data'])} records.")
        print("Sample Record:", res['data'][0])
    else:
        print("\nFailed or No Data.")

if __name__ == "__main__":
    debug_history()
