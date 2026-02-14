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

    def test_returns_value_on_success(self):
        """Test that successful function returns its value"""
        @log_and_suppress("Operation failed")
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_passes_arguments(self):
        """Test that arguments are passed to decorated function"""
        @log_and_suppress("Operation failed")
        def function_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = function_with_args("x", "y", c="z")
        assert result == "x-y-z"

    def test_passes_kwargs(self):
        """Test that kwargs are passed to decorated function"""
        @log_and_suppress("Operation failed")
        def function_with_kwargs(**kwargs):
            return kwargs

        result = function_with_kwargs(a=1, b=2)
        assert result == {"a": 1, "b": 2}

    def test_default_log_level_is_warning(self):
        """Test that default log level is warning"""
        with patch('core.error_handling.logger') as mock_logger:
            @log_and_suppress("Test message")
            def failing_func():
                raise RuntimeError("Error")

            failing_func()
            assert mock_logger.warning.called

    def test_custom_log_level_error(self):
        """Test custom log level 'error'"""
        with patch('core.error_handling.logger') as mock_logger:
            @log_and_suppress("Test message", level="error")
            def failing_func():
                raise RuntimeError("Error")

            failing_func()
            assert mock_logger.error.called

    def test_custom_log_level_info(self):
        """Test custom log level 'info'"""
        with patch('core.error_handling.logger') as mock_logger:
            @log_and_suppress("Test message", level="info")
            def failing_func():
                raise RuntimeError("Error")

            failing_func()
            assert mock_logger.info.called

    def test_custom_log_level_debug(self):
        """Test custom log level 'debug'"""
        with patch('core.error_handling.logger') as mock_logger:
            @log_and_suppress("Test message", level="debug")
            def failing_func():
                raise RuntimeError("Error")

            failing_func()
            assert mock_logger.debug.called

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring"""
        @log_and_suppress("Test")
        def my_function():
            """This is my function"""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function"

    def test_multiple_exception_types_in_raise_on(self):
        """Test multiple exception types in raise_on tuple"""
        @log_and_suppress("Test", raise_on=(ValueError, KeyError))
        def raise_key_error():
            raise KeyError("Key not found")

        with pytest.raises(KeyError):
            raise_key_error()


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

    def test_no_error_message_no_logging(self):
        """Test that no logging happens when error_message is None"""
        with patch('core.error_handling.logger') as mock_logger:
            @safe_execute(fallback_value="default")
            def failing_func():
                raise ValueError("Error")

            result = failing_func()

            assert result == "default"
            # Logger should not be called when error_message is None
            assert not mock_logger.warning.called

    def test_custom_fallback_values(self):
        """Test various fallback value types"""
        test_cases = [
            (0, 0),
            ("", ""),
            ([], []),
            ({}, {}),
            (None, None),
            (False, False),
        ]
        for fallback, expected in test_cases:
            @safe_execute(fallback_value=fallback)
            def failing_func():
                raise ValueError("Error")

            assert failing_func() == expected

    def test_custom_log_level(self):
        """Test custom log level"""
        with patch('core.error_handling.logger') as mock_logger:
            @safe_execute(fallback_value=0, error_message="Test", log_level="error")
            def failing_func():
                raise ValueError("Error")

            failing_func()
            assert mock_logger.error.called

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name"""
        @safe_execute(fallback_value=0)
        def my_function():
            """My docstring"""
            pass

        assert my_function.__name__ == "my_function"

    def test_passes_arguments(self):
        """Test that arguments are passed correctly"""
        @safe_execute(fallback_value=0)
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5


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

    def test_suppresses_exception_by_default(self):
        """Test that exception is suppressed by default"""
        # Should not raise, just log
        with ErrorContext("Operation failed"):
            raise ValueError("Test error")

        # If we get here, exception was suppressed
        assert True

    def test_custom_exception_types_logs_error(self):
        """Test that non-matching exception types are logged as error"""
        with patch('core.error_handling.logger') as mock_logger:
            # KeyError is not in exception_types, so it should log as error
            with ErrorContext("Test", exception_types=(ValueError,)):
                raise KeyError("Different exception")

            # Should have logged an error (not warning)
            assert mock_logger.error.called

    def test_returns_self_on_enter(self):
        """Test that __enter__ returns self"""
        ctx = ErrorContext("Test")
        with ctx as returned:
            assert returned is ctx

    def test_context_with_reraise_false_logs_warning(self):
        """Test that suppressed exception logs warning"""
        with patch('core.error_handling.logger') as mock_logger:
            with ErrorContext("Test message"):
                raise ValueError("Test error")

            # Should have logged a warning
            assert mock_logger.warning.called


class TestLogAndSuppressIntegration:
    """Integration tests for log_and_suppress"""

    def test_nested_decorators(self):
        """Test nested decorated functions"""
        @log_and_suppress("Outer failed")
        def outer():
            @log_and_suppress("Inner failed")
            def inner():
                raise ValueError("Inner error")
            return inner()

        result = outer()
        assert result is None

    def test_exception_chaining(self):
        """Test that original exception info is preserved in log"""
        with patch('core.error_handling.logger') as mock_logger:
            @log_and_suppress("Failed")
            def func():
                raise ValueError("Original error")

            func()

            # Check that the log call includes exception info
            call_args = mock_logger.warning.call_args
            assert "ValueError" in str(call_args) or "Original error" in str(call_args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
