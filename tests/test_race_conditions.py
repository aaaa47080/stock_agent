"""Tests for atomic race condition fixes in quota/limit systems.

Verifies that check-and-increment functions are atomic
and prevent TOCTOU race conditions.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestCheckAndIncrementMessage:
    """Tests for atomic message limit check-and-increment."""

    def test_returns_can_send_true_when_under_limit(self):
        from core.database.messages.limits import check_and_increment_message

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=20
            ):
                result = check_and_increment_message("user1", False)

        assert result["can_send"] is True
        assert result["used"] == 5
        assert result["remaining"] == 15
        assert result["limit"] == 20
        mock_conn.commit.assert_called_once()

    def test_returns_can_send_false_when_at_limit(self):
        from core.database.messages.limits import check_and_increment_message

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (20,)
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=20
            ):
                result = check_and_increment_message("user1", False)

        assert result["can_send"] is True
        assert result["used"] == 20
        assert result["remaining"] == 0

    def test_returns_can_send_false_when_over_limit(self):
        from core.database.messages.limits import check_and_increment_message

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (21,)
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=20
            ):
                result = check_and_increment_message("user1", False)

        assert result["can_send"] is False
        assert result["used"] == 21
        assert result["remaining"] == 0

    def test_premium_unlimited_when_config_is_none(self):
        from core.database.messages.limits import check_and_increment_message

        with patch(
            "core.database.messages.limits._get_message_config", return_value=None
        ):
            result = check_and_increment_message("user1", True)

        assert result["can_send"] is True
        assert result["limit"] == -1

    def test_rollback_on_error(self):
        from core.database.messages.limits import check_and_increment_message

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=20
            ):
                with pytest.raises(Exception, match="DB error"):
                    check_and_increment_message("user1", False)

        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_uses_single_sql_statement(self):
        from core.database.messages.limits import check_and_increment_message

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=20
            ):
                check_and_increment_message("user1", False)

        sql_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert len(sql_calls) == 1
        assert "RETURNING message_count" in sql_calls[0]


class TestCheckAndIncrementGreeting:
    """Tests for atomic greeting limit check-and-increment."""

    def test_returns_can_send_true_when_under_limit(self):
        from core.database.messages.limits import check_and_increment_greeting

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=5
            ):
                result = check_and_increment_greeting("user1", True)

        assert result["can_send"] is True
        assert result["used"] == 3
        assert result["remaining"] == 2
        mock_conn.commit.assert_called_once()

    def test_rejects_non_premium(self):
        from core.database.messages.limits import check_and_increment_greeting

        result = check_and_increment_greeting("user1", False)
        assert result["can_send"] is False
        assert result["error"] == "premium_only"

    def test_returns_can_send_false_when_over_limit(self):
        from core.database.messages.limits import check_and_increment_greeting

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (6,)
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=5
            ):
                result = check_and_increment_greeting("user1", True)

        assert result["can_send"] is False
        assert result["remaining"] == 0


class TestCheckAndIncrementToolQuota:
    """Tests for atomic tool quota check-and-increment."""

    def test_returns_true_when_under_limit(self):
        from core.database.tools import check_and_increment_tool_quota

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("daily", 10, None, 50),  # tools_catalog row
            (5,),  # usage after increment
        ]
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.database.tools.get_connection", return_value=mock_conn):
            result = check_and_increment_tool_quota("user1", "some_tool", "premium")

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_returns_false_when_over_limit(self):
        from core.database.tools import check_and_increment_tool_quota

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("daily", 10, None, 10),  # tools_catalog: limit=10
            (11,),  # usage exceeds limit
        ]
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.database.tools.get_connection", return_value=mock_conn):
            result = check_and_increment_tool_quota("user1", "some_tool", "free")

        assert result is False

    def test_returns_true_for_unlimited_tool(self):
        from core.database.tools import check_and_increment_tool_quota

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("unlimited", None, None, None)
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.database.tools.get_connection", return_value=mock_conn):
            result = check_and_increment_tool_quota("user1", "some_tool", "free")

        assert result is True

    def test_returns_true_when_tool_not_found(self):
        from core.database.tools import check_and_increment_tool_quota

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.database.tools.get_connection", return_value=mock_conn):
            result = check_and_increment_tool_quota("user1", "nonexistent", "free")

        assert result is True

    def test_rollback_on_error(self):
        from core.database.tools import check_and_increment_tool_quota

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.database.tools.get_connection", return_value=mock_conn):
            result = check_and_increment_tool_quota("user1", "some_tool", "free")

        assert result is True  # Error fallback: allow
        mock_conn.rollback.assert_called_once()

    def test_uses_returning_clause(self):
        from core.database.tools import check_and_increment_tool_quota

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("daily", 10, None, 50),
            (1,),
        ]
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.database.tools.get_connection", return_value=mock_conn):
            check_and_increment_tool_quota("user1", "tool1", "free")

        sql_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        increment_sql = sql_calls[1]
        assert "RETURNING call_count" in increment_sql


class TestLegacyFunctionsStillWork:
    """Verify legacy check/increment functions still work for backward compatibility."""

    def test_check_message_limit_read_only(self):
        from core.database.messages.limits import check_message_limit

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            with patch(
                "core.database.messages.limits._get_message_config", return_value=20
            ):
                result = check_message_limit("user1", False)

        assert result["can_send"] is True
        assert result["used"] == 5
        mock_conn.commit.assert_not_called()

    def test_increment_message_count(self):
        from core.database.messages.limits import increment_message_count

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.messages.limits.get_connection", return_value=mock_conn
        ):
            increment_message_count("user1")

        mock_conn.commit.assert_called_once()
