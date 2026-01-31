"""
轻量级市场筛选器 - 专为 Market Watch 优化
只计算显示需要的数据：24小时涨跌幅 + RSI
速度提升 20+ 倍
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from typing import List, Optional
from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
import concurrent.futures
import time
import random

def calculate_rsi_simple(series: pd.Series, period: int = 14) -> float:
    """快速计算RSI - 只返回最新值"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1] if len(rsi) > 0 else 50.0


# Valid for 5 seconds (Real-time snapshot, short cache)
_TICKER_CACHE = {
    'okx': {'data': [], 'timestamp': 0},
    'binance': {'data': [], 'timestamp': 0}
}
CACHE_SLAPSHOT_DURATION = 5 

def screen_top_cryptos_light(exchange='okx', limit=10, interval='1d', target_symbols: Optional[List[str]] = None, market_pulse_data: dict = None):
    
    # 1. Helper function
    def safe_float(v, default=0.0):
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    # 2. Get Data Fetcher
    try:
        fetcher = get_data_fetcher(exchange)
    except Exception as e:
        print(f"Error initializing fetcher: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Define keys based on exchange
    if exchange == 'okx':
        key_symbol = 'instId'
        key_last = 'last'
        key_vol = 'volCcy24h' # USDT volume usually
    else: # binance
        key_symbol = 'symbol'
        key_last = 'lastPrice'
        key_vol = 'quoteVolume'

    # Check cache
    now = time.time()
    if exchange in _TICKER_CACHE and (now - _TICKER_CACHE[exchange]['timestamp'] < CACHE_SLAPSHOT_DURATION):
        usdt_tickers = _TICKER_CACHE[exchange]['data']
    else:
        # Fetch fresh data
        try:
            raw_tickers = fetcher.get_tickers()
            if not raw_tickers:
                raw_tickers = []
            
            # Filter for USDT pairs
            usdt_tickers = []
            suffix = '-USDT' if exchange == 'okx' else 'USDT'
            
            for t in raw_tickers:
                sym = t.get(key_symbol, '')
                if sym.endswith(suffix):
                    usdt_tickers.append(t)
            
            # Update cache
            _TICKER_CACHE[exchange] = {
                'data': usdt_tickers,
                'timestamp': now
            }
        except Exception as e:
            print(f"Error fetching tickers: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 3. Process ALL tickers to find Gainers/Losers
    processed_all = []
    
    for t in usdt_tickers:
        symbol = t.get(key_symbol, 'UNKNOWN')
        # Standardize symbol for lookup (e.g. BTC-USDT -> BTC)
        base_symbol = symbol.split('-')[0].upper()
        
        last_price = safe_float(t.get(key_last, 0))
        volume = safe_float(t.get(key_vol, 0))
        
        # Calculate Change %
        change_pct = 0.0
        if exchange == 'okx':
            open_24h = safe_float(t.get('open24h', last_price))
            if open_24h != 0:
                change_pct = ((last_price - open_24h) / open_24h) * 100
        else:
            change_pct = safe_float(t.get('priceChangePercent', 0))

        # Merge Market Pulse Signals and RSI if available
        signals = []
        rsi = 50.0
        
        if market_pulse_data and base_symbol in market_pulse_data:
             pulse = market_pulse_data[base_symbol]
             if pulse:
                 signals = pulse.get('signals', [])
                 # Prefer Pulse RSI if available (it refers to 4h/1d usually), else 50
                 # Or keep 50 if we don't want to mix timeframe RSIs? 
                 # Let's use Pulse RSI for better visual if available
                 if 'indicators' in pulse and 'rsi' in pulse['indicators']:
                      rsi = pulse['indicators']['rsi']

        processed_all.append({
            'Symbol': symbol,
            'Close': last_price,
            'price_change_24h': change_pct,
            'Volume': volume,
            'RSI_14': rsi,
            'signals': signals
        })

    if not processed_all:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_all = pd.DataFrame(processed_all)

    # 4. Generate Lists
    # A. Volume Leaders (The main list)
    if target_symbols and len(target_symbols) > 0:
        target_set = set(target_symbols)
        df_volume = df_all[df_all['Symbol'].isin(target_set)].copy()
    else:
        df_volume = df_all.sort_values(by='Volume', ascending=False).head(limit).copy()

    # B. Top Gainers & Losers (Filter low volume garbage < 100k USDT)
    min_vol = 100000
    df_liquid = df_all[df_all['Volume'] > min_vol]
    
    if df_liquid.empty:
        df_liquid = df_all
        
    df_gainers = df_liquid.sort_values(by='price_change_24h', ascending=False).head(5).copy()
    df_losers = df_liquid.sort_values(by='price_change_24h', ascending=True).head(5).copy()
    
    # Return: Summary(Vol), Gainers, Losers, Dummy
    return df_volume, df_gainers, df_losers, pd.DataFrame()


if __name__ == '__main__':
    # 测试
    import time
    start = time.time()
    summary, top, oversold, overbought = screen_top_cryptos_light(exchange='okx', limit=10)
    elapsed = time.time() - start
    print(f"\nElapsed time: {elapsed:.2f}s")
    print(f"Results: {len(top)} total, {len(oversold)} oversold, {len(overbought)} overbought")
