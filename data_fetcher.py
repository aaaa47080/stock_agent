import requests
import pandas as pd
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

class SymbolNotFoundError(Exception):
    """Custom exception for when a trading symbol is not found on the exchange."""
    pass

class BinanceDataFetcher:
    def __init__(self):
        self.spot_base_url = "https://api.binance.com/api/v3"
        self.futures_base_url = "https://fapi.binance.com/fapi/v1"

    def _make_request(self, base_url, endpoint, params=None):
        """Helper to make HTTP requests and handle common errors."""
        try:
            response = requests.get(base_url + endpoint, params=params)
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            # Check for specific Binance error codes for symbol not found
            if response.status_code == 400 and "Invalid symbol" in response.text:
                raise SymbolNotFoundError(f"Symbol not found or invalid: {params.get('symbol', 'N/A')} on {base_url}") from http_err
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
    """OKX 交易所數據獲取器"""

    def __init__(self):
        self.base_url = "https://www.okx.com/api/v5"

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
        try:
            url = self.base_url + endpoint
            response = requests.get(url, params=params, timeout=10)
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
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
            return None

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
        df['Open_time'] = pd.to_numeric(df['Open_time'], errors='coerce')
        df['Open'] = pd.to_numeric(df['Open'], errors='coerce')
        df['High'] = pd.to_numeric(df['High'], errors='coerce')
        df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')

        # 添加 Binance 格式的額外欄位（用於兼容性）
        df['Close_time'] = df['Open_time'] + 1000  # 簡化處理
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

        df['Open_time'] = pd.to_numeric(df['Open_time'], errors='coerce')
        df['Open'] = pd.to_numeric(df['Open'], errors='coerce')
        df['High'] = pd.to_numeric(df['High'], errors='coerce')
        df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')

        df['Close_time'] = df['Open_time'] + 1000
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
    # Example usage for Binance Spot
    print("--- Testing Binance Spot API ---")
    binance_fetcher = get_data_fetcher("binance")
    
    # Test with a valid symbol
    try:
        spot_klines_df = binance_fetcher.get_historical_klines('BTCUSDT', '1d')
        if spot_klines_df is not None and not spot_klines_df.empty:
            print("Successfully fetched Binance Spot K-line data for BTCUSDT")
            print(spot_klines_df.tail())
        else:
            print("Failed to fetch Binance Spot K-line data for BTCUSDT (unexpected)")
    except SymbolNotFoundError as e:
        print(f"Caught expected error for BTCUSDT: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Caught unexpected request error for BTCUSDT: {e}")

    # Test with an invalid symbol
    print("\n--- Testing Binance Spot API with INVALID symbol ---")
    try:
        spot_klines_df_invalid = binance_fetcher.get_historical_klines('INVALIDPAIR', '1d')
        if spot_klines_df_invalid is not None and not spot_klines_df_invalid.empty:
            print("Successfully fetched Binance Spot K-line data for INVALIDPAIR (unexpected)")
        else:
            print("Failed to fetch Binance Spot K-line data for INVALIDPAIR (expected)")
    except SymbolNotFoundError as e:
        print(f"Caught expected error for INVALIDPAIR: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Caught unexpected request error for INVALIDPAIR: {e}")


    print("\n" + "="*50 + "\n")

    # Example usage for Binance Futures
    print("--- Testing Binance Futures API ---")
    # Test with a valid symbol
    try:
        futures_klines_df, funding_rate = binance_fetcher.get_futures_data('BTCUSDT', '1d')
        if futures_klines_df is not None and not futures_klines_df.empty:
            print("Successfully fetched Binance Futures K-line data for BTCUSDT")
            print(futures_klines_df.tail())
        if funding_rate:
            print("\nSuccessfully fetched Binance Funding Rate data for BTCUSDT")
            print(funding_rate)
        else:
            print("Failed to fetch Binance Futures K-line data or funding rate for BTCUSDT (unexpected)")
    except SymbolNotFoundError as e:
        print(f"Caught expected error for BTCUSDT: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Caught unexpected request error for BTCUSDT: {e}")

    # Test with an invalid symbol
    print("\n--- Testing Binance Futures API with INVALID symbol ---")
    try:
        futures_klines_df_invalid, funding_rate_invalid = binance_fetcher.get_futures_data('INVALIDPAIR', '1d')
        if futures_klines_df_invalid is not None and not futures_klines_df_invalid.empty:
            print("Successfully fetched Binance Futures K-line data for INVALIDPAIR (unexpected)")
        else:
            print("Failed to fetch Binance Futures K-line data for INVALIDPAIR (expected)")
    except SymbolNotFoundError as e:
        print(f"Caught expected error for INVALIDPAIR: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Caught unexpected request error for INVALIDPAIR: {e}")

    print("\n" + "="*50 + "\n")

    # Example usage for OKX Spot
    print("--- Testing OKX Spot API (Placeholder) ---")
    okx_fetcher = get_data_fetcher("okx")
    okx_spot_klines_df = okx_fetcher.get_historical_klines('PI-USDT', '1d')
    if okx_spot_klines_df is not None and not okx_spot_klines_df.empty:
        print("Successfully (placeholder) fetched OKX Spot K-line data for PI-USDT")
        print(okx_spot_klines_df.tail())
    else:
        print("Failed to fetch OKX Spot K-line data for PI-USDT (as expected for placeholder)")
