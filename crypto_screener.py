
import os
import pandas as pd
from datetime import datetime
from data_fetcher import get_data_fetcher, SymbolNotFoundError
from indicator_calculator import add_technical_indicators
from data_processor import (
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

def screen_top_cryptos(exchange='binance', limit=30, interval='1d'):
    """
    Fetches, analyzes, and ranks the top cryptocurrencies, returning DataFrames
    for UI display and saving reports.
    """
    print(f"Starting crypto screening process for {exchange.upper()}...")

    # 1. Initialize data fetcher
    try:
        fetcher = get_data_fetcher(exchange)
    except ValueError as e:
        print(f"Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 2. Get top symbols
    top_symbols = fetcher.get_top_symbols(limit=limit)
    if not top_symbols:
        print("Could not retrieve top symbols. Exiting.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 3. Fetch and analyze data for each symbol
    all_analysis_results = []
    all_raw_data = []
    for symbol in top_symbols:
        print(f"Fetching and analyzing data for {symbol}...")
        try:
            klines_df = fetcher.get_historical_klines(symbol, interval, limit=100)
            if klines_df is not None:
                # Store raw data
                klines_df_copy = klines_df.copy()
                klines_df_copy['symbol'] = symbol
                all_raw_data.append(klines_df_copy)

                # Perform analysis
                analysis_result = analyze_symbol_data(klines_df, symbol)
                if analysis_result:
                    all_analysis_results.append(analysis_result)
            else:
                print(f"No data returned for {symbol}.")
        except SymbolNotFoundError:
            print(f"Symbol {symbol} not found or not supported. Skipping.")
        except Exception as e:
            print(f"An unexpected error occurred for {symbol}: {e}")

    if not all_analysis_results:
        print("No analysis was performed. Exiting.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 4. Create a summary DataFrame for ranking
    summary_list = []
    for result in all_analysis_results:
        summary_item = {
            "Symbol": result["symbol"],
            "Current Price": result["price_info"]["當前價格"],
            "7d Change %": result["price_info"]["7天價格變化百分比"],
            "Trend": result["market_structure"]["趨勢"],
            "Volatility": result["market_structure"]["波動率"],
            "RSI_14": result["technical_indicators"]["RSI_14"],
            "Support": result["key_levels"]["支撐位"],
            "Resistance": result["key_levels"]["壓力位"],
        }
        summary_list.append(summary_item)
    
    summary_df = pd.DataFrame(summary_list)

    # 5. Save raw data and summary report
    output_dir = "analysis_results"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save raw data
    raw_data_file = os.path.join(output_dir, f"top_{limit}_crypto_raw_data_{timestamp}.csv")
    if all_raw_data:
        combined_raw_df = pd.concat(all_raw_data, ignore_index=True)
        combined_raw_df.to_csv(raw_data_file, index=False)
        print(f"\nRaw data for {len(all_raw_data)} symbols saved to: {raw_data_file}")

    # Save summary report
    summary_file = os.path.join(output_dir, f"top_{limit}_crypto_summary_report_{timestamp}.csv")
    summary_df.to_csv(summary_file, index=False)
    
    print(f"Analysis summary report saved to: {summary_file}")

    # 6. Prepare DataFrames for Gradio output
    top_performers = summary_df.sort_values(by="7d Change %", ascending=False).head(10)
    oversold = summary_df[summary_df["RSI_14"] < 40].sort_values(by="RSI_14", ascending=True).head(10)
    overbought = summary_df[summary_df["RSI_14"] > 70].sort_values(by="RSI_14", ascending=False).head(10)

    # Print to console as well
    print("\n\n--- Top 10 Cryptos by 7-day Performance ---")
    print(top_performers.to_string(index=False))
    print("\n--- Top 10 Most Oversold (RSI < 40) ---")
    print(oversold.to_string(index=False))
    print("\n--- Top 10 Most Overbought (RSI > 70) ---")
    print(overbought.to_string(index=False))

    return summary_df, top_performers, oversold, overbought


if __name__ == '__main__':
    # You can choose 'binance' or 'okx'
    screen_top_cryptos(exchange='binance', limit=30, interval='1d')
