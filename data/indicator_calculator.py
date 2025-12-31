import pandas as pd
import pandas_ta as ta
from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
import sys # Import sys for exiting gracefully

def add_technical_indicators(df):
    """
    Adds a comprehensive set of technical indicators to the DataFrame.

    :param df: The DataFrame with K-line data.
    :return: The DataFrame with added indicator columns.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Add a comprehensive set of indicators using pandas_ta
    
    # Trend Indicators
    df.ta.macd(close='Close', fast=12, slow=26, signal=9, append=True)
    df.ta.ema(close='Close', length=12, append=True)
    df.ta.ema(close='Close', length=26, append=True)
    df.ta.sma(close='Close', length=7, append=True)   # MA7
    df.ta.sma(close='Close', length=25, append=True)  # MA25
    df.ta.adx(length=14, append=True) # Average Directional Index

    # Momentum Indicators
    df.ta.rsi(close='Close', length=14, append=True)
    df.ta.stoch(length=14, k=3, d=3, append=True) # Stochastic Oscillator

    # Volume Indicators
    df.ta.obv(close=df['Close'], volume=df['Volume'], append=True) # On-Balance Volume
    
    # Volatility Indicators
    df.ta.bbands(close='Close', length=20, std=2, append=True)
    df.ta.atr(length=14, append=True) # Average True Range

    return df

if __name__ == '__main__':
    # Example usage to verify all indicators
    symbol = 'BTCUSDT'
    interval = '1d'
    
    # 1. Fetch data
    binance_fetcher = get_data_fetcher("binance")
    klines_df = None
    try:
        klines_df = binance_fetcher.get_historical_klines(symbol, interval, limit=100)
    except SymbolNotFoundError as e:
        print(f"Error fetching data: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while fetching data: {e}")
        sys.exit(1)
    
    if klines_df is not None and not klines_df.empty:
        print(f"Successfully fetched {len(klines_df)} data points for {symbol}.")
        
        # 2. Add all indicators
        df_with_indicators = add_technical_indicators(klines_df)
        
        print("\nDataFrame with a full set of technical indicators (last 5 rows):")
        
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 120)

        # Columns to display (include the new ones)
        display_cols = [
            'Close_time', 'Close', 'Volume',
            'RSI_14', 'MACD_12_26_9', # Momentum
            'ADX_14', # Trend Strength
            'OBV', # Volume
            'BBU_20_2.0_2.0', 'ATR_14', # Volatility
            'STOCHk_14_3_3', 'STOCHd_14_3_3' # Stochastic
        ]
        
        # Filter out columns that might not exist in the first few rows (due to calculation window)
        existing_cols = [col for col in display_cols if col in df_with_indicators.columns]
        
        print(df_with_indicators[existing_cols].tail())
    else:
        print("No data fetched. Exiting.")
        sys.exit(1)

