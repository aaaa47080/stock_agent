import sys
import os
import unittest
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_processor import fetch_and_process_klines, build_market_data_package

class TestBacktestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()

    def test_market_data_package_contains_backtest(self):
        symbol = "BTC-USDT"
        exchange = "okx"
        interval = "1d"
        limit = 100
        
        print(f"Fetching data for {symbol}...")
        df, funding_info = fetch_and_process_klines(symbol, interval, limit, "spot", exchange)
        
        print("Building market data package...")
        package = build_market_data_package(
            df=df,
            symbol=symbol,
            market_type="spot",
            exchange=exchange,
            leverage=1,
            funding_rate_info=funding_info
        )
        
        self.assertIn('歷史回測', package)
        backtest_results = package['歷史回測']
        self.assertIsInstance(backtest_results, list)
        self.assertTrue(len(backtest_results) > 0)
        
        print("Backtest results found in package:")
        for res in backtest_results[:2]: # Show summary and first strategy
            print(f" - {res}")

if __name__ == '__main__':
    unittest.main()
