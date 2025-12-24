from data.data_fetcher import get_data_fetcher
import pandas as pd

def get_klines(symbol: str, exchange: str = "binance", interval: str = "1d", limit: int = 100):
    """
    Fetch historical klines for a given symbol and exchange.
    Returns a DataFrame with columns: timestamp, open, high, low, close, volume
    """
    try:
        fetcher = get_data_fetcher(exchange)
        df = fetcher.get_historical_klines(symbol, interval, limit)
        
        if df is None or df.empty:
            return None
            
        # Rename columns to match what api_server.py expects
        # data_fetcher returns: Open_time, Open, High, Low, Close, Volume...
        # api_server expects: timestamp, open, high, low, close
        
        rename_map = {
            'Open_time': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        
        df = df.rename(columns=rename_map)
        
        # Ensure only required columns are returned and they are in the correct format
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        # Filter columns that exist in the dataframe
        cols_to_keep = [col for col in required_cols if col in df.columns]
        df = df[cols_to_keep]
        
        return df
        
    except Exception as e:
        print(f"Error in get_klines: {e}")
        return None
