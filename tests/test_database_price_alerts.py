"""Tests for price_alerts database functions."""
import pytest
from unittest.mock import MagicMock, patch
from core.database.price_alerts import (
    create_price_alerts_table,
    create_alert,
    get_user_alerts,
    delete_alert,
    get_active_alerts,
    mark_alert_triggered,
)


class TestCreateAlert:
    def test_create_alert_returns_dict_with_id(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)  # count=0, under limit
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            result = create_alert(
                user_id="u1",
                symbol="AAPL",
                market="us_stock",
                condition="above",
                target=200.0,
                repeat=False,
            )

        assert "id" in result
        assert result["symbol"] == "AAPL"
        assert result["market"] == "us_stock"
        assert result["condition"] == "above"
        assert result["target"] == 200.0
        assert result["repeat"] == 0

    def test_invalid_market_raises(self):
        with pytest.raises(ValueError, match="market"):
            create_alert("u1", "AAPL", "invalid_market", "above", 200.0)

    def test_invalid_condition_raises(self):
        with pytest.raises(ValueError, match="condition"):
            create_alert("u1", "AAPL", "us_stock", "invalid_cond", 200.0)


class TestGetUserAlerts:
    def test_returns_list(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            result = get_user_alerts("u1")

        assert isinstance(result, list)


class TestDeleteAlert:
    def test_delete_returns_bool(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            result = delete_alert("alert-id", "u1")

        assert isinstance(result, bool)


class TestMarkAlertTriggered:
    def test_one_shot_deletes_alert(self):
        """repeat=False alert should be deleted when triggered."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            mark_alert_triggered("alert-id", repeat=False)

        # Should call DELETE
        call_args = mock_cursor.execute.call_args[0][0]
        assert "DELETE" in call_args.upper()

    def test_persistent_sets_triggered_flag(self):
        """repeat=True alert should set triggered=1, not delete."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("core.database.price_alerts.get_connection", return_value=mock_conn):
            mark_alert_triggered("alert-id", repeat=True)

        call_args = mock_cursor.execute.call_args[0][0]
        assert "UPDATE" in call_args.upper()
