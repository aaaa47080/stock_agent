import requests
import pandas as pd
import time
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

class SymbolNotFoundError(Exception):
    """Custom exception for when a trading symbol is not found on the exchange."""
    pass

class BinanceDataFetcher:
    """
    Fetches market data from Binance using public API endpoints.
    Does NOT require API keys. strictly for public market data.
    """
    def __init__(self):
        self.spot_base_url = "https://api.binance.com/api/v3"
        self.futures_base_url = "https://fapi.binance.com/fapi/v1"
        # Rate limiting for Binance API - initialize request tracking
        self.last_request_time = time.time()
        # Binance API weight mapping - different endpoints have different weights
        self.endpoint_weights = {
            "/exchangeInfo": 40,   # High weight endpoint - this is likely what's causing the ban
            "/klines": 2,          # Standard weight for klines
            "/ticker/24hr": 2,     # Standard weight for ticker
            "/premiumIndex": 2,    # Standard weight for funding rate
        }
        # Conservative rate limits to avoid bans
        self.max_weight_per_minute = 600  # Reduced to be more conservative
        self.current_weight_in_window = 0
        self.weight_window_start = time.time()

    def _enforce_rate_limit(self, endpoint="/klines"):
        """Enforce rate limiting to avoid hitting Binance API limits."""
        current_time = time.time()

        # Get the weight for this endpoint
        weight = self.endpoint_weights.get(endpoint, 1)

        # Check if we're in a new minute window
        if current_time - self.weight_window_start >= 60:
            self.current_weight_in_window = 0
            self.weight_window_start = current_time

        # Check if adding this request's weight would exceed the limit
        if self.current_weight_in_window + weight > self.max_weight_per_minute:
            # Calculate how long to wait until the next window
            sleep_time = 60 - (current_time - self.weight_window_start)
            if sleep_time > 0:
                time.sleep(sleep_time)
            # Reset the window
            self.current_weight_in_window = 0
            self.weight_window_start = time.time()

        # Add this request's weight to the current window
        self.current_weight_in_window += weight

        # Also enforce minimum delay between requests
        time_since_last_request = current_time - self.last_request_time
        min_delay = 0.05  # 50ms minimum delay between requests
        if time_since_last_request < min_delay:
            sleep_time = min_delay - time_since_last_request
            time.sleep(sleep_time)

        # Update the last request time
        self.last_request_time = time.time()

    def _make_request(self, base_url, endpoint, params=None):
        """Helper to make HTTP requests and handle common errors."""
        # Extract just the endpoint path (without query parameters) for rate limiting
        endpoint_path = endpoint.split('?')[0] if '?' in endpoint else endpoint
        # Enforce rate limiting before making request
        self._enforce_rate_limit(endpoint_path)

        # Try the request with retries for rate limit errors
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = requests.get(base_url + endpoint, params=params)
                response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
                return response.json()
            except requests.exceptions.HTTPError as http_err:
                # Check for specific Binance error codes for symbol not found
                if response.status_code == 400 and "Invalid symbol" in response.text:
                    raise SymbolNotFoundError(f"Symbol not found or invalid: {params.get('symbol', 'N/A')} on {base_url}") from http_err
                # Handle specific rate limit error codes from Binance
                elif response.status_code == 418 or ("-1003" in response.text):
                    print(f"Binance API rate limit exceeded: {response.text}")
                    print("Aborting request to prevent ban escalation.")
                    return None
                print(f"HTTP error occurred: {http_err} - Response: {response.text}")
                return None
            except requests.exceptions.ConnectionError as conn_err:
                print(f"Connection error occurred: {conn_err}")
                return None
            except requests.exceptions.Timeout as timeout_err:
                print(f"Timeout error occurred: {timeout_err}")
                return None
            except requests.exceptions.RequestException as req_err:
                print(f"An unexpected request error occurred: {req_err}")
                return None

    def check_symbol_availability(self, symbol, market_type='spot'):
        """
        Checks if a given symbol is available on Binance for the specified market type.
        Raises SymbolNotFoundError if the symbol is not found.
        """
        base_url = self.spot_base_url if market_type == 'spot' else self.futures_base_url
        endpoint = "/exchangeInfo"
        
        try:
            exchange_info = self._make_request(base_url, endpoint)
            if exchange_info:
                # Binance returns symbols in a list under the "symbols" key
                for s in exchange_info.get("symbols", []):
                    if s["symbol"] == symbol and s["status"] == "TRADING":
                        return True
                raise SymbolNotFoundError(f"Symbol '{symbol}' not found or not trading on Binance {market_type} market.")
            # If exchange_info is None, it means _make_request already handled an error
            # In this case, we can't definitively say the symbol is not found,
            # but rather that we couldn't even check exchange info.
            raise requests.exceptions.RequestException(f"Could not retrieve exchange info for {market_type} market to check symbol '{symbol}'.")
        except SymbolNotFoundError:
            raise # Re-raise the specific error
        except requests.exceptions.RequestException as req_err:
            print(f"Error checking symbol availability for {symbol} on {market_type} market: {req_err}")
            raise # Re-raise the request error to be handled upstream
        except Exception as e:
            print(f"An unexpected error occurred while checking symbol availability for {symbol} on {market_type} market: {e}")
            raise requests.exceptions.RequestException(f"An unexpected error occurred: {e}")

    def get_top_symbols(self, limit=30, quote_asset='USDT'):
        """
        Gets the top trading symbols by 24-hour quote volume from Binance Spot.
        """
        endpoint = "/ticker/24hr"
        print(f"Fetching top {limit} symbols from Binance, quoted in {quote_asset}...")
        
        all_tickers = self._make_request(self.spot_base_url, endpoint)
        
        if all_tickers:
            # Filter for symbols that are quoted in the desired asset (e.g., USDT)
            usdt_tickers = [t for t in all_tickers if t['symbol'].endswith(quote_asset)]
            
            # Sort by quote volume in descending order
            # The 'quoteVolume' is a string, so it needs to be converted to float
            sorted_tickers = sorted(usdt_tickers, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            
            # Get the top 'limit' symbols
            top_symbols = [t['symbol'] for t in sorted_tickers[:limit]]
            
            print(f"Found top {len(top_symbols)} symbols: {top_symbols}")
            return top_symbols
            
        print("Could not retrieve tickers to determine top symbols.")
        return []

    def get_all_symbols(self, quote_asset='USDT'):
        """Get all trading symbols quoted in the specified asset."""
        endpoint = "/exchangeInfo"
        info = self._make_request(self.spot_base_url, endpoint)
        if info:
            return [s['symbol'] for s in info['symbols'] if s['symbol'].endswith(quote_asset) and s['status'] == 'TRADING']
        return []

    def get_historical_klines(self, symbol, interval, limit=1000, start_str=None):
        """
        Get historical K-line/candlestick data for a symbol from Binance Spot API.
        """
        self.check_symbol_availability(symbol, market_type='spot') # Check symbol availability first

        endpoint = "/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start_str:
            params['startTime'] = int(pd.to_datetime(start_str).timestamp() * 1000)
        
        data = self._make_request(self.spot_base_url, endpoint, params)
        
        if data:
            df = pd.DataFrame(data, columns=[
                'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume', 
                'Close_time', 'Quote_asset_volume', 'Number_of_trades', 
                'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore'
            ])
            
            df['Open_time'] = pd.to_datetime(df['Open_time'], unit='ms')
            df['Close_time'] = pd.to_datetime(df['Close_time'], unit='ms')
            
            numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'Quote_asset_volume', 
                            'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            return df
        return None

    def get_futures_data(self, symbol, interval, limit=1000):
        """
        Get historical K-line/candlestick data and funding rate for a symbol from Binance Futures API.
        """
        self.check_symbol_availability(symbol, market_type='futures') # Check symbol availability first

        klines_df = None
        funding_rate_info = {}

        # 1. Fetch K-lines from fapi/v1/klines
        klines_params = {"symbol": symbol, "interval": interval, "limit": limit}
        data = self._make_request(self.futures_base_url, "/klines", klines_params)
        
        if data:
            klines_df = pd.DataFrame(data, columns=[
                'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume', 
                'Close_time', 'Quote_asset_volume', 'Number_of_trades', 
                'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore'
            ])
            
            klines_df['Open_time'] = pd.to_datetime(klines_df['Open_time'], unit='ms')
            klines_df['Close_time'] = pd.to_datetime(klines_df['Close_time'], unit='ms')
            
            numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'Quote_asset_volume', 
                            'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume']
            for col in numeric_cols:
                klines_df[col] = pd.to_numeric(klines_df[col], errors='coerce')

        # 2. Fetch funding rate from fapi/v1/premiumIndex
        funding_params = {"symbol": symbol}
        data = self._make_request(self.futures_base_url, "/premiumIndex", funding_params)

        if data:
            funding_rate_info = {
                "last_funding_rate": float(data.get("lastFundingRate", 0.0)),
                "next_funding_time": pd.to_datetime(data.get("nextFundingTime", 0), unit='ms').isoformat(),
            }
        else:
            funding_rate_info = {"error": "Failed to fetch funding rate"}

        return klines_df, funding_rate_info

class OkxDataFetcher:
    """
    OKX 交易所數據獲取器
    Uses public API endpoints only. No API keys required.
    """

    def __init__(self):
        self.base_url = os.getenv("OKX_BASE_URL", "https://www.okx.com/api/v5")

    def _convert_interval(self, interval):
        """
        將 Binance 格式的時間間隔轉換為 OKX 格式

        Binance: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w
        OKX: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W
        """
        interval_map = {
            '1m': '1m',
            '3m': '3m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1H',
            '2h': '2H',
            '4h': '4H',
            '6h': '6H',
            '12h': '12H',
            '1d': '1D',
            '1w': '1W',
        }
        return interval_map.get(interval.lower(), '1D')

    def _make_request(self, endpoint, params=None):
        """發送 HTTP 請求到 OKX API"""
        proxies = None
        https_proxy = os.getenv("HTTPS_PROXY")
        if https_proxy:
            proxies = {"http": https_proxy, "https": https_proxy}
            print(f"🕵️ 使用代理: {https_proxy}")

        try:
            # 處理 base_url 和 endpoint 的組合
            # 檢查是否 base_url 已包含版本信息
            if "/api/v5" in self.base_url:
                # 如果 base_url 已包含版本信息，直接附加 endpoint
                url = self.base_url + endpoint
            else:
                # 如果 base_url 沒有版本信息，添加 API 版本前綴
                url = self.base_url + "/api/v5" + endpoint

            response = requests.get(url, params=params, timeout=20, proxies=proxies)
            response.raise_for_status()

            data = response.json()

            # OKX API 返回格式: {"code":"0","msg":"","data":[...]}
            if data.get('code') == '0':
                return data.get('data', [])
            else:
                error_msg = data.get('msg', 'Unknown error')
                print(f"OKX API 錯誤: {error_msg}")
                return None

        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 400:
                raise SymbolNotFoundError(f"Symbol not found on OKX: {params.get('instId', 'N/A')}") from http_err
            print(f"HTTP error occurred: {http_err}")
            return None
        except requests.exceptions.ProxyError as proxy_err:
            print(f"代理錯誤: 無法連接到代理伺服器 {https_proxy}。請檢查您的代理設定和網路。")
            print(f"詳細錯誤: {proxy_err}")
            return None
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
            return None


    def get_top_symbols(self, limit=30, quote_asset='USDT'):
        """
        Gets the top trading symbols by 24-hour volume from OKX Spot.
        OKX symbol format is 'BTC-USDT'.
        """
        endpoint = "/market/tickers"
        params = {'instType': 'SPOT'}
        print(f"Fetching top {limit} symbols from OKX, quoted in {quote_asset}...")

        all_tickers = self._make_request(endpoint, params)
        
        if all_tickers:
            # Filter for symbols quoted in the desired asset (e.g., USDT)
            usdt_tickers = [t for t in all_tickers if t['instId'].endswith(f'-{quote_asset}')]
            
            # Sort by 24h volume in quote currency (volCcy24h)
            # The value is a string, so it needs to be converted to float
            sorted_tickers = sorted(usdt_tickers, key=lambda x: float(x.get('volCcy24h', 0)), reverse=True)
            
            # Get the top 'limit' symbols
            top_symbols = [t['instId'] for t in sorted_tickers[:limit]]
            
            print(f"Found top {len(top_symbols)} symbols: {top_symbols}")
            return top_symbols
            
        print("Could not retrieve tickers from OKX to determine top symbols.")
        return []

    def get_all_symbols(self, quote_asset='USDT'):
        """Get all trading symbols quoted in the specified asset."""
        endpoint = "/public/instruments"
        params = {'instType': 'SPOT'}
        print(f"Fetching all SPOT symbols from OKX, filtering by {quote_asset}...")
        data = self._make_request(endpoint, params)
        if data:
            # OKX usually has quoteCcy field, let's use it for better accuracy
            symbols = [s['instId'] for s in data if (s.get('quoteCcy') == quote_asset or s['instId'].endswith(f'-{quote_asset}')) and s.get('state') == 'live']
            print(f"OKX: Found {len(symbols)} symbols matching {quote_asset}")
            return symbols
        print("OKX: Failed to retrieve symbols from instruments endpoint.")
        return []

    def check_symbol_availability(self, symbol, inst_type='SPOT'):
        """
        Checks if a given symbol is available on OKX.
        Raises SymbolNotFoundError if the symbol is not found.
        """
        endpoint = "/public/instruments"
        params = {'instType': inst_type, 'instId': symbol}
        
        try:
            instrument_data = self._make_request(endpoint, params)
            # The API returns a list. If it's empty, the symbol doesn't exist.
            if instrument_data and len(instrument_data) > 0:
                # Double-check the instrument ID and its state.
                if instrument_data[0]['instId'] == symbol and instrument_data[0]['state'] == 'live':
                    return True
            
            # If the list is empty or conditions are not met, raise the error.
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found or not live on OKX {inst_type} market.")

        except requests.exceptions.RequestException as req_err:
            print(f"Error checking symbol availability for {symbol} on OKX: {req_err}")
            raise # Re-raise to be handled upstream


    def get_historical_klines(self, symbol, interval, limit=100):
        """
        獲取 OKX 現貨市場的 K 線數據

        Args:
            symbol: 交易對符號 (OKX 格式，如 "BTC-USDT")
            interval: 時間間隔 (如 "1d", "1h")
            limit: 數據條數

        Returns:
            DataFrame with columns: Open_time, Open, High, Low, Close, Volume, etc.
        """
        self.check_symbol_availability(symbol, inst_type='SPOT') # Check symbol availability first
        
        endpoint = "/market/candles"

        # 轉換時間間隔
        okx_interval = self._convert_interval(interval)

        # OKX API 參數
        params = {
            'instId': symbol,
            'bar': okx_interval,
            'limit': min(limit, 300)  # OKX 最多返回 300 條
        }

        data = self._make_request(endpoint, params)

        if not data:
            return None

        # OKX 返回格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        # 轉換為與 Binance 相同的格式
        df = pd.DataFrame(data, columns=[
            'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Volume_currency', 'Volume_quote', 'Confirm'
        ])

        # 轉換數據類型，處理空字符串
        df['Open_time'] = pd.to_datetime(pd.to_numeric(df['Open_time']), unit='ms')
        df['Open'] = pd.to_numeric(df['Open'], errors='coerce')
        df['High'] = pd.to_numeric(df['High'], errors='coerce')
        df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')

        # 添加 Binance 格式的額外欄位（用於兼容性）
        df['Close_time'] = df['Open_time'] + pd.to_timedelta(okx_interval.replace('H', 'h')) - pd.to_timedelta(1, 'ms')
        df['Quote_asset_volume'] = df['Volume_quote']
        df['Number_of_trades'] = 0  # OKX 不提供
        df['Taker_buy_base_asset_volume'] = 0  # OKX 不提供
        df['Taker_buy_quote_asset_volume'] = 0  # OKX 不提供
        df['Ignore'] = 0

        # 反轉順序（OKX 返回的是從新到舊）
        df = df.iloc[::-1].reset_index(drop=True)

        # 只保留需要的欄位
        df = df[[
            'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close_time', 'Quote_asset_volume', 'Number_of_trades',
            'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore'
        ]]

        return df

    def get_futures_data(self, symbol, interval, limit=100):
        """
        獲取 OKX 合約市場的 K 線數據和資金費率

        Args:
            symbol: 交易對符號 (如 "BTC-USDT-SWAP")
            interval: 時間間隔
            limit: 數據條數

        Returns:
            (DataFrame, funding_rate_dict)
        """
        # OKX 合約符號格式: BTC-USDT-SWAP
        if not symbol.endswith('-SWAP'):
            # 如果是現貨格式 (BTC-USDT)，轉換為合約格式
            symbol = symbol + '-SWAP'

        self.check_symbol_availability(symbol, inst_type='SWAP') # Check symbol availability first

        # 獲取 K 線數據
        endpoint = "/market/candles"
        okx_interval = self._convert_interval(interval)

        params = {
            'instId': symbol,
            'bar': okx_interval,
            'limit': min(limit, 300)
        }

        klines_data = self._make_request(endpoint, params)

        if not klines_data:
            return None, {}

        # 轉換 K 線數據
        df = pd.DataFrame(klines_data, columns=[
            'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Volume_currency', 'Volume_quote', 'Confirm'
        ])

        df['Open_time'] = pd.to_datetime(pd.to_numeric(df['Open_time']), unit='ms')
        df['Open'] = pd.to_numeric(df['Open'], errors='coerce')
        df['High'] = pd.to_numeric(df['High'], errors='coerce')
        df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')

        df['Close_time'] = df['Open_time'] + pd.to_timedelta(okx_interval.replace('H', 'h')) - pd.to_timedelta(1, 'ms')
        df['Quote_asset_volume'] = df['Volume_quote']
        df['Number_of_trades'] = 0
        df['Taker_buy_base_asset_volume'] = 0
        df['Taker_buy_quote_asset_volume'] = 0
        df['Ignore'] = 0

        df = df.iloc[::-1].reset_index(drop=True)

        df = df[[
            'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close_time', 'Quote_asset_volume', 'Number_of_trades',
            'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore'
        ]]

        # 獲取資金費率
        funding_rate_info = self._get_funding_rate(symbol)

        return df, funding_rate_info

    def _get_funding_rate(self, symbol):
        """
        獲取資金費率

        Args:
            symbol: 合約交易對符號 (如 "BTC-USDT-SWAP")

        Returns:
            Dict with funding rate information
        """
        endpoint = "/public/funding-rate"

        params = {
            'instId': symbol
        }

        data = self._make_request(endpoint, params)

        if not data or len(data) == 0:
            return {}

        # OKX 返回格式: [{"fundingRate":"0.0001","fundingTime":"...","nextFundingRate":"0.0001","nextFundingTime":"..."}]
        rate_data = data[0]

        # 安全轉換，處理空字符串
        def safe_float(value, default=0.0):
            try:
                return float(value) if value and value != '' else default
            except (ValueError, TypeError):
                return default

        return {
            'current_funding_rate': safe_float(rate_data.get('fundingRate')),
            'next_funding_rate': safe_float(rate_data.get('nextFundingRate')),
            'funding_time': rate_data.get('fundingTime', ''),
            'next_funding_time': rate_data.get('nextFundingTime', '')
        }

def get_data_fetcher(exchange: str):
    """
    Factory function to get the appropriate data fetcher.
    """
    if exchange.lower() == "binance":
        return BinanceDataFetcher()
    elif exchange.lower() == "okx":
        return OkxDataFetcher()
    else:
        raise ValueError(f"Unsupported exchange: {exchange}")

if __name__ == '__main__':
    # 僅保留成功的冒煙測試，移除會混淆使用者的錯誤測試
    print("--- 啟動交易所數據獲取器測試 ---")
    
    # 測試 OKX
    try:
        okx_fetcher = get_data_fetcher("okx")
        symbols = okx_fetcher.get_top_symbols(limit=5)
        print(f"✅ OKX 測試成功，前 5 大幣種: {symbols}")
    except Exception as e:
        print(f"❌ OKX 測試失敗: {e}")

    print("\n" + "="*30 + "\n")

    # 測試 Binance
    try:
        binance_fetcher = get_data_fetcher("binance")
        symbols = binance_fetcher.get_top_symbols(limit=5)
        if symbols:
            print(f"✅ Binance 測試成功: {symbols}")
        else:
            print("ℹ️ Binance 目前處於頻率限制或封禁中，跳過測試。")
    except Exception as e:
        print(f"ℹ️ Binance 測試跳過 (預期限制): {e}")


