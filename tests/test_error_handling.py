"""
Tests for error handling utilities
"""
import pytest
from unittest.mock import patch, Mock, MagicMock
from core.error_handling import log_and_suppress, safe_execute, ErrorContext


class TestLogAndSuppress:
    """Tests for @log_and_suppress decorator"""

    def test_logs_exception_and_returns_none(self):
        """Test that exception is logged and None is returned"""
        with patch('core.error_handling.logger') as mock_logger:
            @log_and_suppress("Operation failed")
            def failing_function():
                raise ValueError("Test error")

            result = failing_function()

            assert result is None
            # Verify warning was logged
            assert mock_logger.warning.called

    def test_does_not_raise_on_specific_exception(self):
        """Test that specific exception types are still raised"""
        @log_and_suppress("Operation failed", raise_on=(ValueError,))
        def function_with_value_error():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            function_with_value_error()

    def test_other_exceptions_suppressed(self):
        """Test that other exceptions are suppressed"""
        with patch('core.error_handling.logger') as mock_logger:
            @log_and_suppress("Operation failed", raise_on=(KeyError,))
            def function_with_value_error():
                raise ValueError("Test error")

            result = function_with_value_error()

            assert result is None
            assert mock_logger.warning.called


class TestSafeExecute:
    """Tests for @safe_execute decorator"""

    def test_returns_fallback_on_error(self):
        """Test that fallback value is returned on exception"""
        with patch('core.error_handling.logger') as mock_logger:
            @safe_execute(fallback_value=0, error_message="Count failed")
            def get_count():
                raise ValueError("Test error")

            result = get_count()

            assert result == 0
            assert mock_logger.warning.called

    def test_returns_result_on_success(self):
        """Test that actual result is returned on success"""
        @safe_execute(fallback_value=0)
        def get_count():
            return 42

        result = get_count()

        assert result == 42


class TestErrorContext:
    """Tests for ErrorContext context manager"""

    def test_context_manager_works(self):
        """Test that ErrorContext works as a context manager"""
        with ErrorContext("Test context"):
            # Should not raise any exception
            pass

        # Should complete without error
        assert True

    def test_reraises_when_requested(self):
        """Test that exception is re-raised when reraise=True"""
        with pytest.raises(ValueError):
            with ErrorContext("Operation failed", reraise=True):
                raise ValueError("Test error")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
