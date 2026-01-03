import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.backtest_engine import BacktestEngine

class TestBacktestEngine(unittest.TestCase):
    def setUp(self):
        # Create a synthetic trending dataset
        dates = pd.date_range(start='2023-01-01', periods=100)
        data = {
            'Open': np.linspace(100, 200, 100),
            'High': np.linspace(105, 205, 100),
            'Low': np.linspace(95, 195, 100),
            'Close': np.linspace(100, 200, 100),
            'Volume': [1000] * 100
        }
        self.df = pd.DataFrame(data, index=dates)
        self.engine = BacktestEngine()

    def test_rsi_strategy(self):
        result = self.engine.run_rsi_strategy(self.df)
        self.assertIn('win_rate', result)
        self.assertIn('total_return', result)
        print(f"RSI Strategy Result: {result}")

    def test_trend_following(self):
        result = self.engine.run_trend_following_strategy(self.df)
        self.assertIn('win_rate', result)
        self.assertIn('total_return', result)
        print(f"Trend Following Result: {result}")

    def test_run_all_strategies(self):
        results = self.engine.run_all_strategies(self.df)
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 1)
        self.assertIn('summary', results[0])
        print(f"All Strategies Summary: {results[0]}")

if __name__ == '__main__':
    unittest.main()
