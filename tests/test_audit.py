"""Tests for centralized audit logging."""

from core.audit import AuditLogger, _sanitize_request_data


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_prepare_payload_normalizes_endpoint_and_method(self):
        """_prepare_payload should normalize endpoint and method with defaults."""
        payload = AuditLogger._prepare_payload(
            action="DELETE POST",
            user_id="user-1",
            resource_type="post",
            resource_id="42",
            endpoint="/api/forum/posts/42",
            method="delete",
            success=True,
        )

        # payload tuple indices: user_id=0, username=1, action=2, resource_type=3,
        # resource_id=4, endpoint=5, method=6, ...
        assert payload[5] == "/api/forum/posts/42"
        assert payload[6] == "DELETE"
        assert payload[2] == "delete_post"

    def test_log_defaults_endpoint_and_method_for_internal_actions(self):
        """Internal audit writes should still populate endpoint and method."""
        payload = AuditLogger._prepare_payload(
            action="token_refresh",
            user_id="user-1",
        )

        # payload tuple indices: endpoint=5, method=6
        assert payload[5] == "system://internal"
        assert payload[6] == "SYSTEM"


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
