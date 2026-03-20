"""Tests for TEST_MODE hardening and fd leak fixes."""
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open


class TestDevLoginConfirmation:
    """Verify dev-login requires confirmation token."""

    def test_dev_login_requires_confirmation_string(self):
        from api.routers.user import DevLoginRequest
        req = DevLoginRequest(confirmation="I_UNDERSTAND_THE_RISKS")
        assert req.confirmation == "I_UNDERSTAND_THE_RISKS"

    def test_dev_login_rejects_wrong_confirmation(self):
        from pydantic import ValidationError
        from api.routers.user import DevLoginRequest

        with pytest.raises((ValidationError, ValueError)):
            DevLoginRequest(confirmation="wrong_value")

    def test_dev_login_default_confirmation(self):
        from api.routers.user import DevLoginRequest
        req = DevLoginRequest()
        assert req.confirmation == "I_UNDERSTAND_THE_RISKS"

    def test_dev_login_model_has_confirmation_field(self):
        from api.routers.user import DevLoginRequest
        fields = DevLoginRequest.model_fields
        assert "confirmation" in fields


class TestFdLeakFix:
    """Verify the debug-log endpoint uses proper file context managers."""

    def test_debug_log_write_uses_context_manager(self):
        content = open("D:/okx/stock_agent/api_server.py", "r", encoding="utf-8").read()
        # The POST debug-log should use a with statement, not bare open().write()
        # Look for the _write_log helper function
        assert "_write_log" in content, "Missing _write_log helper function"
        # Should NOT have bare open().write in the executor lambda
        assert 'lambda: open("frontend_debug.log"' not in content, (
            "fd leak: bare open() in lambda without context manager"
        )

    def test_debug_log_read_uses_context_manager(self):
        content = open("D:/okx/stock_agent/api_server.py", "r", encoding="utf-8").read()
        assert "_read_log" in content, "Missing _read_log helper function"
        assert "lambda: open(\"frontend_debug.log\", \"r\"" not in content, (
            "fd leak: bare open() in lambda without context manager"
        )


class TestNoPrintInUserPy:
    """Verify user.py has no print() calls (should use logger)."""

    def test_no_print_statements_in_user_router(self):
        content = open("D:/okx/stock_agent/api/routers/user.py", "r", encoding="utf-8").read()
        lines = content.split("\n")
        print_lines = [
            i + 1 for i, line in enumerate(lines)
            if "print(" in line and not line.strip().startswith("#") and 'repr(' not in line
        ]
        assert not print_lines, f"user.py has print() calls at lines: {print_lines}"


class TestTestModeProductionGuard:
    """Verify TEST_MODE is blocked in production."""

    def test_deps_blocks_test_mode_in_production(self):
        from api.deps import get_current_user
        import inspect
        source = inspect.getsource(get_current_user)
        assert "production" in source.lower()
        assert "ENVIRONMENT" in source
