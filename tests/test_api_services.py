"""
Tests for API services in api/services.py
"""

from unittest.mock import patch

import pytest

from api.services import (
    _build_market_pulse_targets,
    _get_cache_timestamps,
    load_funding_rate_cache,
    load_market_pulse_cache,
    save_funding_rate_cache,
    save_market_pulse_cache,
)


class TestMarketPulseCache:
    """Tests for Market Pulse cache functions"""

    def test_save_market_pulse_cache_success(self):
        """Test successful cache save"""
        with patch("api.services.set_cache") as mock_set:
            with patch("api.services.MARKET_PULSE_CACHE", {"BTC": {}}):
                save_market_pulse_cache(silent=True)
                mock_set.assert_called_once()

    def test_save_market_pulse_cache_with_logging(self):
        """Test cache save with logging"""
        with patch("api.services.set_cache") as _:
            with patch("api.services.MARKET_PULSE_CACHE", {}):
                with patch("api.services.logger") as mock_logger:
                    save_market_pulse_cache(silent=False)
                    mock_logger.info.assert_called()

    def test_save_market_pulse_cache_error(self):
        """Test cache save error handling"""
        with patch("api.services.set_cache", side_effect=Exception("DB error")):
            with patch("api.services.MARKET_PULSE_CACHE", {}):
                with patch("api.services.logger") as mock_logger:
                    # Should not raise
                    save_market_pulse_cache()
                    mock_logger.error.assert_called()

    def test_load_market_pulse_cache_success(self):
        """Test successful cache load"""
        with patch("api.services.get_cache") as mock_get:
            mock_get.return_value = {"BTC": {"price": 50000}}
            with patch("api.services.MARKET_PULSE_CACHE", {}):
                with patch("api.services.logger"):
                    load_market_pulse_cache()

    def test_load_market_pulse_cache_no_data(self):
        """Test cache load with no data"""
        with patch("api.services.get_cache", return_value=None):
            with patch("api.services.MARKET_PULSE_CACHE", {}):
                load_market_pulse_cache()

    def test_load_market_pulse_cache_error(self):
        """Test cache load error handling"""
        with patch("api.services.get_cache", side_effect=Exception("DB error")):
            with patch("api.services.logger") as mock_logger:
                # Should not raise
                load_market_pulse_cache()
                mock_logger.error.assert_called()


class TestFundingRateCache:
    """Tests for Funding Rate cache functions"""

    def test_save_funding_rate_cache_success(self):
        """Test successful funding rate cache save"""
        with patch("api.services.set_cache") as mock_set:
            with patch("api.services.FUNDING_RATE_CACHE", {"data": {"BTC": 0.01}}):
                save_funding_rate_cache(silent=True)
                mock_set.assert_called_once()

    def test_save_funding_rate_cache_with_logging(self):
        """Test funding rate cache save with logging"""
        with patch("api.services.set_cache"):
            with patch("api.services.FUNDING_RATE_CACHE", {"data": {}}):
                with patch("api.services.logger") as mock_logger:
                    save_funding_rate_cache(silent=False)
                    mock_logger.info.assert_called()

    def test_save_funding_rate_cache_error(self):
        """Test funding rate cache save error handling"""
        with patch("api.services.set_cache", side_effect=Exception("DB error")):
            with patch("api.services.FUNDING_RATE_CACHE", {"data": {}}):
                with patch("api.services.logger") as mock_logger:
                    # Should not raise
                    save_funding_rate_cache()
                    mock_logger.error.assert_called()

    def test_load_funding_rate_cache_success(self):
        """Test successful funding rate cache load"""
        with patch("api.services.get_cache") as mock_get:
            mock_get.return_value = {"BTC": 0.01}
            with patch("api.services.FUNDING_RATE_CACHE", {}):
                with patch("api.services.logger"):
                    result = load_funding_rate_cache()
                    assert result is True

    def test_load_funding_rate_cache_no_data(self):
        """Test funding rate cache load with no data"""
        with patch("api.services.get_cache", return_value=None):
            with patch("api.services.FUNDING_RATE_CACHE", {}):
                result = load_funding_rate_cache()
                assert result is False

    def test_load_funding_rate_cache_error(self):
        """Test funding rate cache load error handling"""
        with patch("api.services.get_cache", side_effect=Exception("DB error")):
            with patch("api.services.logger") as mock_logger:
                result = load_funding_rate_cache()
                assert result is False
                mock_logger.error.assert_called()


class TestCacheDataFlow:
    """Tests for cache data flow"""

    def test_save_and_load_cycle(self):
        """Test save and load cycle"""
        test_data = {"BTC": {"price": 50000, "change": 5.0}}

        # Simulate save
        with patch("api.services.set_cache") as mock_set:
            with patch("api.services.MARKET_PULSE_CACHE", test_data):
                save_market_pulse_cache()
                mock_set.assert_called_with("MARKET_PULSE", test_data)

        # Simulate load
        with patch("api.services.get_cache", return_value=test_data):
            with patch("api.services.MARKET_PULSE_CACHE", {}) as _:
                load_market_pulse_cache()
                # Cache should be updated


class TestMarketPulseTargetSanitization:
    """Tests for market pulse target symbol sanitization."""

    def test_build_targets_skips_invalid_symbols(self):
        with patch("api.services.MARKET_PULSE_TARGETS", ["BTC", "PROGRESS"]):
            targets = _build_market_pulse_targets(["ETH-USDT", "LOADING", "eth"])

        assert targets == {"BTC", "ETH"}


class TestMarketPulseTimestampParsing:
    """Tests for timezone-safe market pulse cache timestamp parsing."""

    def test_get_cache_timestamps_normalizes_naive_timestamps_to_utc(self):
        timestamps = _get_cache_timestamps(
            {
                "BTC": {"timestamp": "2026-03-27T02:38:23"},
                "ETH": {"timestamp": "2026-03-27T02:38:23+00:00"},
            }
        )

        assert len(timestamps) == 2
        assert all(ts.tzinfo is not None for ts in timestamps)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
