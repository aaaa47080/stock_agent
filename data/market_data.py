from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
import pandas as pd
import sys
import os

# Add project root to path to ensure core.config can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from core.config import SUPPORTED_EXCHANGES
except ImportError:
    SUPPORTED_EXCHANGES = ["binance", "okx"] # Fallback

def get_klines(symbol: str, exchange: str = "binance", interval: str = "1d", limit: int = 100):
    """
    Fetch historical klines for a given symbol.
    If the symbol is not found on the specified exchange, it tries other supported exchanges.
    Returns a DataFrame with columns: timestamp, open, high, low, close, volume
    """
    
    # List of exchanges to try. Start with the requested one, then others.
    exchanges_to_try = [exchange] + [ex for ex in SUPPORTED_EXCHANGES if ex != exchange]
    
    last_exception = None
    
    for current_exchange in exchanges_to_try:
        try:
            fetcher = get_data_fetcher(current_exchange)
            
            # --- Symbol Normalization ---
            # Automatically adapt symbol format for the specific exchange
            normalized_symbol = symbol.upper()
            if current_exchange.lower() == 'binance':
                # Binance: BTCUSDT (No hyphen)
                if '-' in normalized_symbol:
                    normalized_symbol = normalized_symbol.replace('-', '')
                if not normalized_symbol.endswith('USDT'):
                    normalized_symbol += 'USDT'
            elif current_exchange.lower() == 'okx':
                # OKX: BTC-USDT (With hyphen)
                if '-' not in normalized_symbol:
                    if normalized_symbol.endswith('USDT'):
                        # If BTCUSDT, convert to BTC-USDT
                        normalized_symbol = normalized_symbol.replace('USDT', '-USDT')
                    else:
                        # If BTC, convert to BTC-USDT
                        normalized_symbol += '-USDT'
            
            # Try to fetch
            df = fetcher.get_historical_klines(normalized_symbol, interval, limit)
            
            if df is not None and not df.empty:
                # Rename columns to match what api_server.py expects
                rename_map = {
                    'Open_time': 'timestamp',
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                }
                
                df = df.rename(columns=rename_map)
                
                # Ensure only required columns are returned
                required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                cols_to_keep = [col for col in required_cols if col in df.columns]
                df = df[cols_to_keep]
                
                return df
                
        except (SymbolNotFoundError, ValueError, Exception) as e:
            last_exception = e
            # Continue to next exchange
            continue
            
    # If we get here, no exchange worked
    print(f"Error in get_klines for {symbol}: {last_exception}")
    return None
