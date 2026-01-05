import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
from typing import List, Optional
from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
from data.indicator_calculator import add_technical_indicators
from data.data_processor import (
    calculate_key_levels,
    analyze_market_structure,
    extract_technical_indicators,
    calculate_price_info,
)

def analyze_symbol_data(df: pd.DataFrame, symbol: str) -> dict:
    """Analyzes a single symbol's dataframe and returns a dictionary of results."""
    if df is None or df.empty:
        return None

    # Add technical indicators
    df_with_indicators = add_technical_indicators(df)
    latest_data = df_with_indicators.iloc[-1]

    # Perform analysis
    analysis = {
        "symbol": symbol,
        "price_info": calculate_price_info(df_with_indicators),
        "technical_indicators": extract_technical_indicators(latest_data),
        "market_structure": analyze_market_structure(df_with_indicators),
        "key_levels": calculate_key_levels(df_with_indicators),
    }
    return analysis

def screen_top_cryptos(exchange='okx', limit=30, interval='1d', target_symbols: Optional[List[str]] = None):
    """
    Fetches, analyzes, and ranks cryptocurrencies.
    
    Args:
        exchange: Exchange name
        limit: Max number of symbols if scanning top market cap
        interval: Timeframe
        target_symbols: Optional list of symbols to analyze exclusively. 
                        If provided, 'limit' is ignored for fetching.
    """
    print(f"Starting crypto screening process for {exchange.upper()}...")

    # 1. Initialize data fetcher
    try:
        fetcher = get_data_fetcher(exchange)
    except ValueError as e:
        print(f"Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 2. Get symbols list
    if target_symbols and len(target_symbols) > 0:
        print(f"Using target list: {target_symbols}")
        # Normalize symbols for the fetcher if needed (simple append)
        # Note: data_fetcher usually expects "BTC" or "BTC-USDT" depending on exchange.
        # Here we assume the input is cleaner "BTC" and fetcher handles suffix, 
        # OR we handle suffix here. Let's try to be smart.
        top_symbols = []
        for s in target_symbols:
            s_clean = s.upper().replace("USDT", "").replace("-", "")
            if exchange == 'okx':
                top_symbols.append(f"{s_clean}-USDT")
            else:
                top_symbols.append(f"{s_clean}USDT")
    else:
        top_symbols = fetcher.get_top_symbols(limit=limit)
        
    if not top_symbols:
        print("Could not retrieve symbols. Exiting.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 3. Fetch and analyze data for each symbol
    all_analysis_results = []
    all_raw_data = []

    import concurrent.futures

    def process_symbol(symbol):
        """Helper function to fetch and analyze a single symbol."""
        try:
            # print(f"Fetching and analyzing data for {symbol}...")
            klines_df = fetcher.get_historical_klines(symbol, interval, limit=100)
            if klines_df is not None:
                # Store raw data
                klines_df_copy = klines_df.copy()
                klines_df_copy['symbol'] = symbol
                
                # Perform analysis
                analysis_result = analyze_symbol_data(klines_df, symbol)
                return klines_df_copy, analysis_result
            else:
                print(f"No data returned for {symbol}.")
                return None, None
        except SymbolNotFoundError:
            print(f"Symbol {symbol} not found or not supported. Skipping.")
            return None, None
        except Exception as e:
            print(f"An unexpected error occurred for {symbol}: {e}")
            return None, None

    # Use ThreadPoolExecutor for parallel execution
    # Determine max workers (reduced to prevent rate limiting/IP bans)
    max_workers = min(len(top_symbols), 3) 
    print(f"Starting parallel analysis with {max_workers} workers...")

    import time
    import random

    def process_symbol_with_delay(symbol):
        # Add random delay to distribute requests and avoid hitting rate limits
        time.sleep(random.uniform(0.5, 2.0)) 
        return process_symbol(symbol)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_symbol = {executor.submit(process_symbol_with_delay, symbol): symbol for symbol in top_symbols}
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                raw_data, analysis_result = future.result()
                if raw_data is not None:
                    all_raw_data.append(raw_data)
                if analysis_result:
                    all_analysis_results.append(analysis_result)
            except Exception as exc:
                print(f'{symbol} generated an exception: {exc}')

    if not all_analysis_results:
        print("No analysis was performed. Exiting.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 4. Create a summary DataFrame for ranking
    summary_list = []
    for result in all_analysis_results:
        # Avoid potential None values in price info
        price_info = result["price_info"] or {}
        market_structure = result["market_structure"] or {}
        tech_indicators = result["technical_indicators"] or {}
        key_levels = result["key_levels"] or {}
        
        # --- 訊號偵測邏輯 ---
        signals = []
        
        # 1. 黃金交叉 (MA7 > MA25)
        ma7 = tech_indicators.get("MA_7", 0)
        ma25 = tech_indicators.get("MA_25", 0)
        # 簡單判定：如果 MA7 > MA25 且差距不大（剛交叉不久），或者我們需要更精確的交叉判定（需要前一根 K 線）
        # 這裡簡化為：只要 MA7 > MA25 就標示為多頭排列，若配合其他指標更強
        if ma7 > ma25:
            # 這裡可以進一步判斷乖離率，避免已經漲太多的
            pass 
            
        # 2. 海龜突破 (價格 > 20日高點)
        current_price = price_info.get("當前價格", 0)
        high_20d = key_levels.get("20日最高價", 9999999)
        if current_price > high_20d:
            signals.append("🐢突破")
            
        # 3. 爆量 (Volume Spike)
        if market_structure.get("爆量", False):
            signals.append("🔥爆量")
            
        # 4. 黃金交叉 (EMA 7/25 or similar) - 這裡用 MA 代替
        # 為了更精確，我們假設 current_price > MA7 > MA25 且 RSI < 70 (未過熱)
        if ma7 > ma25 and tech_indicators.get("RSI_14", 50) < 70:
            # 如果只是單純多頭排列，給個小星星；如果是剛交叉（比較難判斷），先給金叉標籤
            # 這裡簡化：多頭排列且強勢
            signals.append("✨金叉")

        # 5. 抄底 (RSI < 30)
        if tech_indicators.get("RSI_14", 50) < 30:
            signals.append("💎抄底")

        summary_item = {
            "Symbol": result["symbol"],
            "Current Price": price_info.get("當前價格", 0),
            "24h Change %": price_info.get("24小時價格變化百分比", 0),
            "7d Change %": price_info.get("7天價格變化百分比", 0),
            "Trend": market_structure.get("趨勢", "Unknown"),
            "Volatility": market_structure.get("波動率", 0),
            "RSI_14": tech_indicators.get("RSI_14", 50),
            "Support": key_levels.get("支撐位", 0),
            "Resistance": key_levels.get("壓力位", 0),
            "Signals": signals  # 新增訊號欄位
        }
        summary_list.append(summary_item)
    
    summary_df = pd.DataFrame(summary_list)

    # 5. [Removed] Save raw data and summary report (Logic removed to keep directory clean)
    # The output_dir logic and CSV saving has been disabled.
    
    # 6. Prepare DataFrames for output
    # Ensure columns are numeric for sorting
    summary_df["24h Change %"] = pd.to_numeric(summary_df["24h Change %"], errors='coerce').fillna(0)
    summary_df["7d Change %"] = pd.to_numeric(summary_df["7d Change %"], errors='coerce').fillna(0)
    summary_df["RSI_14"] = pd.to_numeric(summary_df["RSI_14"], errors='coerce').fillna(50)

    top_performers = summary_df.sort_values(by="24h Change %", ascending=False).head(10)
    oversold = summary_df[summary_df["RSI_14"] < 40].sort_values(by="RSI_14", ascending=True).head(10)
    overbought = summary_df[summary_df["RSI_14"] > 70].sort_values(by="RSI_14", ascending=False).head(10)

    return summary_df, top_performers, oversold, overbought


if __name__ == '__main__':
    # You can choose 'binance' or 'okx'
    screen_top_cryptos(exchange='binance', limit=30, interval='1d')