"""Tests for TEST_MODE hardening and fd leak fixes."""

import os

import pytest


def _read_source(relative_path):
    """Read source file relative to project root."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(root, relative_path)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


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
    """Verify the debug-log endpoint uses safe file handling."""

    def test_debug_log_uses_rotating_handler(self):
        content = _read_source("api_server.py")
        assert "RotatingFileHandler" in content, (
            "debug-log should use RotatingFileHandler to prevent unbounded file growth"
        )
        assert "maxBytes" in content, "RotatingFileHandler should have maxBytes limit"

    def test_debug_log_read_has_size_limit(self):
        content = _read_source("api_server.py")
        assert "100 * 1024" in content, (
            "debug-log GET endpoint should limit read size to 100KB"
        )


class TestNoPrintInUserPy:
    """Verify user.py has no print() calls (should use logger)."""

    def test_no_print_statements_in_user_router(self):
        content = _read_source(os.path.join("api", "routers", "user.py"))
        lines = content.split("\n")
        print_lines = [
            i + 1
            for i, line in enumerate(lines)
            if "print(" in line
            and not line.strip().startswith("#")
            and "repr(" not in line
        ]
        assert not print_lines, f"user.py has print() calls at lines: {print_lines}"


class TestTestModeProductionGuard:
    """Verify TEST_MODE is blocked in production."""

    def test_deps_blocks_test_mode_in_production(self):
        import inspect

        from api.deps import get_current_user

        source = inspect.getsource(get_current_user)
        assert "production" in source.lower()
        assert "ENVIRONMENT" in source
