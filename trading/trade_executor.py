import argparse
import glob
import os
import sys

# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.okx_auto_trader import execute_trade_from_analysis_file

def find_latest_analysis_file(pattern: str) -> str:
    """Finds the latest file matching a glob pattern."""
    files = glob.glob(pattern)
    if not files:
        # If not found in the current directory, check in the parent directory
        files = glob.glob(os.path.join("..", pattern))
    
    if not files:
        return None
        
    return max(files, key=os.path.getctime)

def main():
    parser = argparse.ArgumentParser(description="OKX Auto-Trader from analysis files.")
    parser.add_argument(
        "--file",
        type=str,
        help="Path to a specific analysis JSON file."
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use the latest analysis file found in the project."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live trading. Without this flag, it runs in simulation mode."
    )
    
    args = parser.parse_args()

    if not args.file and not args.latest:
        parser.error("You must specify either --file or --latest.")

    file_to_execute = args.file
    if args.latest:
        print("[INFO] Searching for the latest analysis file...")
        # Pattern to find the batch analysis files
        latest_file = find_latest_analysis_file("trading_decisions_batch_*.json")
        if not latest_file:
            print("[ERROR] No recent analysis files found.")
            return
        print(f"[INFO] Found latest analysis file: {latest_file}")
        file_to_execute = latest_file

    if file_to_execute:
        execute_trade_from_analysis_file(file_to_execute, live_trading=args.live)

if __name__ == "__main__":
    main()
