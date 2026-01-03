import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tools import backtest_strategy_tool

def test_tool_output():
    load_dotenv()
    print("Testing backtest_strategy_tool...")
    
    # Run tool for BTC
    result = backtest_strategy_tool.invoke({
        "symbol": "BTC",
        "interval": "1d",
        "period": 30
    })
    
    print("\n--- TOOL OUTPUT START ---")
    print(result)
    print("--- TOOL OUTPUT END ---\n")
    
    if "回測報告" in result and "勝率" in result:
        print("SUCCESS: Tool returned a valid formatted report.")
    else:
        print("FAILED: Tool output missing key information.")

if __name__ == "__main__":
    test_tool_output()

