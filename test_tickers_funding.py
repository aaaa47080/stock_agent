
import os
import sys
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading.okx_api_connector import OKXAPIConnector

def test_tickers():
    api = OKXAPIConnector()
    print("Fetching SWAP tickers...")
    res = api.get_tickers("SWAP")
    
    if res.get("code") == "0" and res.get("data"):
        first_item = res["data"][0]
        print(f"Total tickers: {len(res['data'])}")
        print("Sample Item Keys:", json.dumps(list(first_item.keys())))
        print("Sample Item Data:", json.dumps(first_item, indent=2))
        
        # Check for funding rate fields
        if "fundingRate" in first_item:
            print("✅ fundingRate FOUND")
        else:
            print("❌ fundingRate NOT FOUND")
            
        if "nextFundingRate" in first_item:
            print("✅ nextFundingRate FOUND")
        else:
            print("❌ nextFundingRate NOT FOUND")
            
    else:
        print("Error:", res)

if __name__ == "__main__":
    test_tickers()
