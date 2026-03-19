"""Tests for centralized audit logging."""

from unittest.mock import MagicMock, patch

from core.audit import AuditLogger, _sanitize_request_data


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_log_with_cursor_uses_shared_insert_path(self):
        """Passing a cursor should avoid opening a separate connection."""
        mock_cursor = MagicMock()

        with patch("core.audit.get_connection") as mock_get_connection:
            AuditLogger.log(
                action="DELETE POST",
                user_id="user-1",
                resource_type="post",
                resource_id="42",
                endpoint="/api/forum/posts/42",
                method="delete",
                success=True,
                cursor=mock_cursor,
            )

        mock_get_connection.assert_not_called()
        execute_args = mock_cursor.execute.call_args[0][1]
        assert execute_args[2] == "delete_post"
        assert execute_args[5] == "/api/forum/posts/42"
        assert execute_args[6] == "DELETE"

    def test_log_defaults_endpoint_and_method_for_internal_actions(self):
        """Internal audit writes should still populate endpoint and method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("core.audit.get_connection", return_value=mock_conn):
            AuditLogger.log(action="token_refresh", user_id="user-1")

        execute_args = mock_cursor.execute.call_args[0][1]
        assert execute_args[5] == "system://internal"
        assert execute_args[6] == "SYSTEM"
        mock_conn.commit.assert_called_once()


class TestSanitizeRequestData:
    """Tests for request-data sanitization."""

    def test_redacts_nested_sensitive_fields(self):
        """Nested tokens and secrets should be removed before audit insert."""
        sanitized = _sanitize_request_data(
            {
                "password": "secret",
                "profile": {"access_token": "abc123", "email": "user@example.com"},
            }
        )

        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["profile"]["access_token"] == "[REDACTED]"
        assert sanitized["profile"]["email"].startswith("use")
