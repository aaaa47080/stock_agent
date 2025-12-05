import argparse
import sys
from graph import app
from reporting import display_full_report
from data_fetcher import SymbolNotFoundError # Import the custom exception

def main():
    """
    主執行函式
    """
    parser = argparse.ArgumentParser(description="Crypto Trading Agent for Dual Market Analysis")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol (e.g., BTCUSDT, ETHUSDT)")
    parser.add_argument("--exchange", type=str, default="binance", help="Exchange to fetch data from (e.g., binance, okx)")
    args = parser.parse_args()

    print("=" * 100)
    print("啟動 TradingAgents (LangGraph 版本) - 雙市場分析")
    print("=" * 100)

    symbol = args.symbol
    exchange = args.exchange # Get exchange from args
    interval = "1d"
    limit = 100
    
    spot_final_state = None
    futures_final_state = None

    try:
        # --- 運行現貨市場分析 ---
        print(f"\n--- 運行現貨市場分析 ({symbol}) ---")
        spot_initial_state = {
            "symbol": symbol,
            "exchange": exchange,
            "interval": interval,
            "limit": limit,
            "market_type": 'spot',
            "leverage": 1, # 現貨槓桿固定為 1x
        }
        spot_final_state = app.invoke(spot_initial_state)
        print(f"\n--- 現貨市場分析完成 ({symbol}) ---")

        # --- 運行合約市場分析 ---
        print(f"\n--- 運行合約市場分析 ({symbol}) ---")
        futures_initial_state = {
            "symbol": symbol,
            "exchange": exchange,
            "interval": interval,
            "limit": limit,
            "market_type": 'futures',
            "leverage": 5, # 合約市場預設槓桿 5x，可在此調整
        }
        futures_final_state = app.invoke(futures_initial_state)
        print(f"\n--- 合約市場分析完成 ({symbol}) ---")

    except SymbolNotFoundError as e:
        print(f"\n錯誤: {e}")
        print("請檢查您提供的交易對符號和交易所是否正確。")
        sys.exit(1) # Exit the program with an error code
    except Exception as e:
        print(f"\n發生未知錯誤: {e}")
        sys.exit(1) # Exit for other unexpected errors

    print("\n\n所有工作流執行完畢。")
    print("=" * 100)

    # 從最終狀態中提取資訊並顯示報告
    # 這裡需要傳遞兩個市場的結果，並由 reporting.py 負責合併顯示
    # Only display report if analysis was successful for at least one market
    if spot_final_state or futures_final_state:
        display_full_report(
            spot_results=spot_final_state,
            futures_results=futures_final_state,
        )
    else:
        print("沒有足夠的數據來生成報告。")

if __name__ == '__main__':
    main()
