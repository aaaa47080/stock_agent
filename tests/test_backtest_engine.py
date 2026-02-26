"""
Tests for backtest engine in analysis/backtest_engine.py
"""
import pytest
import pandas as pd
import numpy as np

from analysis.backtest_engine import BacktestEngine, TradeRecord


class TestTradeRecord:
    """Tests for TradeRecord dataclass"""

    def test_create_trade_record(self):
        """Test creating a trade record"""
        record = TradeRecord(
            entry_price=100.0,
            exit_price=110.0,
            pnl_pct=10.0,
            holding_bars=5
        )
        assert record.entry_price == 100.0
        assert record.exit_price == 110.0
        assert record.pnl_pct == 10.0
        assert record.holding_bars == 5

    def test_negative_pnl(self):
        """Test trade record with negative PnL"""
        record = TradeRecord(
            entry_price=100.0,
            exit_price=90.0,
            pnl_pct=-10.0,
            holding_bars=3
        )
        assert record.pnl_pct == -10.0


class TestEvaluateSignalQuality:
    """Tests for _evaluate_signal_quality static method"""

    def test_sample_insufficient(self):
        """Test when sample is insufficient (< 3 trades)"""
        result = BacktestEngine._evaluate_signal_quality(
            win_rate=60, profit_factor=2.0, max_drawdown=5, total_trades=2
        )
        assert result == "樣本不足"

    def test_excellent_quality(self):
        """Test excellent quality signal (score >= 5)"""
        result = BacktestEngine._evaluate_signal_quality(
            win_rate=65, profit_factor=2.5, max_drawdown=8, total_trades=10
        )
        assert result == "優秀"

    def test_good_quality(self):
        """Test good quality signal (score >= 3)"""
        result = BacktestEngine._evaluate_signal_quality(
            win_rate=55, profit_factor=1.6, max_drawdown=15, total_trades=10
        )
        assert result == "良好"

    def test_neutral_quality(self):
        """Test neutral quality signal (score >= 1)"""
        result = BacktestEngine._evaluate_signal_quality(
            win_rate=50, profit_factor=1.2, max_drawdown=25, total_trades=5
        )
        assert result == "中性"

    def test_weak_quality(self):
        """Test weak quality signal (score < 1)"""
        result = BacktestEngine._evaluate_signal_quality(
            win_rate=40, profit_factor=0.8, max_drawdown=30, total_trades=5
        )
        assert result == "偏弱"

    def test_boundary_win_rate_60(self):
        """Test boundary condition for win rate >= 60"""
        result = BacktestEngine._evaluate_signal_quality(
            win_rate=60, profit_factor=2.0, max_drawdown=10, total_trades=5
        )
        assert result == "優秀"

    def test_boundary_win_rate_50(self):
        """Test boundary condition for win rate >= 50"""
        # win_rate=50 gives +1, profit_factor=2.0 gives +2, max_drawdown=10 gives +2
        # Total score = 5 = "優秀"
        result = BacktestEngine._evaluate_signal_quality(
            win_rate=50, profit_factor=2.0, max_drawdown=10, total_trades=5
        )
        assert result == "優秀"


class TestCalculatePerformance:
    """Tests for calculate_performance static method"""

    def test_no_trades(self):
        """Test when there are no trades"""
        signals = pd.Series([0, 0, 0, 0, 0])
        prices = pd.Series([100, 101, 102, 101, 100])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        assert result["total_trades"] == 0
        assert result["win_rate"] == 0.0
        assert result["signal_quality"] == "無交易信號"

    def test_single_profitable_trade(self):
        """Test single profitable trade"""
        # Buy signal at index 0, sell signal at index 2
        signals = pd.Series([1, 0, -1, 0, 0])
        prices = pd.Series([100, 105, 110, 108, 105])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        assert result["total_trades"] == 1
        assert result["win_rate"] == 100.0  # One winning trade
        assert result["total_return"] > 0

    def test_single_losing_trade(self):
        """Test single losing trade"""
        signals = pd.Series([1, 0, -1, 0, 0])
        prices = pd.Series([100, 98, 95, 93, 90])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        assert result["total_trades"] == 1
        assert result["win_rate"] == 0.0  # No winning trades

    def test_multiple_trades(self):
        """Test multiple trades"""
        # Need more data points for multiple complete trades
        # Loop goes to len-1, so need enough bars for 2 complete trades
        signals = pd.Series([1, 0, -1, 0, 1, 0, -1, 0])
        prices = pd.Series([100, 105, 110, 108, 100, 102, 105, 104])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        assert result["total_trades"] == 2

    def test_strategy_name_preserved(self):
        """Test that strategy name is preserved in result"""
        signals = pd.Series([0, 0, 0])
        prices = pd.Series([100, 101, 102])

        result = BacktestEngine.calculate_performance(signals, prices, "CustomStrategy")

        assert result["strategy"] == "CustomStrategy"

    def test_returns_required_fields(self):
        """Test that all required fields are present"""
        signals = pd.Series([1, 0, -1])
        prices = pd.Series([100, 105, 110])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        required_fields = [
            "strategy", "total_trades", "win_rate", "total_return",
            "avg_return", "profit_factor", "max_drawdown", "sharpe_ratio",
            "avg_holding_bars", "signal_quality"
        ]
        for field in required_fields:
            assert field in result

    def test_without_risk_metrics(self):
        """Test calculation without risk metrics"""
        signals = pd.Series([0, 0, 0])
        prices = pd.Series([100, 101, 102])

        result = BacktestEngine.calculate_performance(
            signals, prices, "Test", include_risk_metrics=False
        )

        assert "strategy" in result


class TestBacktestEngineEdgeCases:
    """Edge case tests for BacktestEngine"""

    def test_empty_signals(self):
        """Test with empty signals series"""
        signals = pd.Series([], dtype=int)
        prices = pd.Series([], dtype=float)

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        assert result["total_trades"] == 0

    def test_all_buy_signals(self):
        """Test with all buy signals (no sell)"""
        signals = pd.Series([1, 1, 1, 1, 1])
        prices = pd.Series([100, 101, 102, 103, 104])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        # Should have no completed trades (position never closed)
        assert result["total_trades"] == 0

    def test_all_sell_signals(self):
        """Test with all sell signals (no buy)"""
        signals = pd.Series([-1, -1, -1, -1, -1])
        prices = pd.Series([100, 99, 98, 97, 96])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        # Should have no trades (never entered position)
        assert result["total_trades"] == 0

    def test_alternating_signals(self):
        """Test alternating buy/sell signals"""
        signals = pd.Series([1, -1, 1, -1, 1])
        prices = pd.Series([100, 105, 100, 105, 100])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        assert result["total_trades"] >= 1

    def test_price_volatility(self):
        """Test with volatile prices"""
        signals = pd.Series([1, 0, 0, -1, 0])
        prices = pd.Series([100, 80, 120, 90, 110])

        result = BacktestEngine.calculate_performance(signals, prices, "Test")

        assert result["total_trades"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
