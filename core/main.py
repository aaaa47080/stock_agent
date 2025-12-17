import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from core.graph import app
from analysis.reporting import display_full_report
from data.data_fetcher import SymbolNotFoundError # Import the custom exception
from analysis.crypto_screener import screen_top_cryptos

def main():
    """
    主執行函式
    """
    parser = argparse.ArgumentParser(
        description="Crypto Trading Agent for Dual Market Analysis and Screening",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
時間週期選項 (--interval):
  1m, 3m, 5m, 15m, 30m     分鐘級別
  1h, 2h, 4h, 6h, 12h      小時級別
  1d, 3d, 1w, 1M           日/周/月級別

範例:
  python main.py --symbol BTCUSDT --interval 1h --limit 200
  python main.py --symbol ETHUSDT --interval 15m --limit 500 --exchange okx
  python main.py --screen
        """
    )
    parser.add_argument("--symbol", type=str, default="BTCUSDT",
                       help="交易對符號 (例如: BTCUSDT, ETHUSDT)")
    parser.add_argument("--exchange", type=str, default="binance",
                       help="交易所 (binance 或 okx)")
    parser.add_argument("--interval", type=str, default="1d",
                       choices=['1m', '3m', '5m', '15m', '30m',
                               '1h', '2h', '4h', '6h', '12h',
                               '1d', '3d', '1w', '1M'],
                       help="K線時間週期 (預設: 1d)")
    parser.add_argument("--limit", type=int, default=100,
                       help="獲取的K線數量 (預設: 100)")
    parser.add_argument("--leverage", type=int, default=5,
                       help="合約市場槓桿倍數 (預設: 5x)")
    parser.add_argument("--screen", action="store_true",
                        help="對排名前30的加密貨幣進行篩選")
    args = parser.parse_args()

    if args.screen:
        screen_top_cryptos(exchange=args.exchange, limit=30, interval=args.interval)
        sys.exit(0)

    print("=" * 100)
    print("啟動 TradingAgents (LangGraph 版本) - 雙市場分析")
    print("=" * 100)
    print(f"📊 分析配置: {args.symbol} | 交易所: {args.exchange} | 週期: {args.interval} | 數量: {args.limit}")
    print("=" * 100)

    symbol = args.symbol
    exchange = args.exchange
    interval = args.interval
    limit = args.limit
    
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
            "leverage": args.leverage, # 從命令行參數讀取
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
