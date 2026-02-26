"""Tests for price alert background checker."""
import pytest
from unittest.mock import patch, MagicMock


class TestIsConditionMet:
    """Test the condition evaluation logic."""

    def test_above_triggered(self):
        from api.alert_checker import is_condition_met
        assert is_condition_met("above", 200.0, current_price=205.0, open_price=195.0) is True

    def test_above_not_triggered(self):
        from api.alert_checker import is_condition_met
        assert is_condition_met("above", 200.0, current_price=195.0, open_price=190.0) is False

    def test_below_triggered(self):
        from api.alert_checker import is_condition_met
        assert is_condition_met("below", 180.0, current_price=175.0, open_price=185.0) is True

    def test_below_not_triggered(self):
        from api.alert_checker import is_condition_met
        assert is_condition_met("below", 180.0, current_price=185.0, open_price=182.0) is False

    def test_change_pct_up_triggered(self):
        from api.alert_checker import is_condition_met
        # 10% up: current=110, open=100
        assert is_condition_met("change_pct_up", 5.0, current_price=110.0, open_price=100.0) is True

    def test_change_pct_up_not_triggered(self):
        from api.alert_checker import is_condition_met
        # 3% up: current=103, open=100
        assert is_condition_met("change_pct_up", 5.0, current_price=103.0, open_price=100.0) is False

    def test_change_pct_down_triggered(self):
        from api.alert_checker import is_condition_met
        # 10% down: current=90, open=100
        assert is_condition_met("change_pct_down", 5.0, current_price=90.0, open_price=100.0) is True

    def test_zero_open_price_returns_false(self):
        from api.alert_checker import is_condition_met
        assert is_condition_met("change_pct_up", 5.0, current_price=105.0, open_price=0.0) is False


class TestBuildAlertMessage:
    def test_above_message(self):
        from api.alert_checker import build_alert_body
        alert = {"symbol": "AAPL", "condition": "above", "target": 200.0}
        msg = build_alert_body(alert, current_price=205.50)
        assert "AAPL" in msg
        assert "205" in msg

    def test_change_pct_message(self):
        from api.alert_checker import build_alert_body
        alert = {"symbol": "BTC", "condition": "change_pct_up", "target": 5.0}
        msg = build_alert_body(alert, current_price=55000.0)
        assert "BTC" in msg
