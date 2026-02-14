"""
Tests for retry utilities
"""
import pytest
from unittest.mock import patch, MagicMock
import time

from utils.retry_utils import retry_on_failure


class TestRetryOnFailure:
    """Tests for retry_on_failure decorator"""

    def test_success_no_retry(self):
        """Test that successful function is not retried"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_then_success(self):
        """Test that function retries on failure and eventually succeeds"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        def eventually_successful_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = eventually_successful_func()
        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")

        with pytest.raises(ValueError, match="Permanent error"):
            always_failing_func()

        assert call_count == 3

    def test_custom_max_retries(self):
        """Test custom max_retries parameter"""
        call_count = 0

        @retry_on_failure(max_retries=5, delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Error")

        with pytest.raises(RuntimeError):
            failing_func()

        assert call_count == 5

    def test_default_parameters(self):
        """Test that default parameters work"""
        call_count = 0

        @retry_on_failure()
        def simple_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Fail")
            return "ok"

        result = simple_func()
        assert result == "ok"
        assert call_count == 2

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring"""

        @retry_on_failure(max_retries=2)
        def my_function():
            """This is my function"""
            return "result"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function"

    def test_passes_arguments(self):
        """Test that arguments are passed correctly to decorated function"""

        @retry_on_failure(max_retries=2, delay=0.01)
        def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = func_with_args("x", "y", c="z")
        assert result == "x-y-z"

    def test_passes_kwargs(self):
        """Test that kwargs are passed correctly"""

        @retry_on_failure(max_retries=2, delay=0.01)
        def func_with_kwargs(**kwargs):
            return kwargs

        result = func_with_kwargs(a=1, b=2)
        assert result == {"a": 1, "b": 2}

    def test_different_exception_types(self):
        """Test handling of different exception types"""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        def func_with_different_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First error")
            elif call_count == 2:
                raise TypeError("Second error")
            return "success"

        result = func_with_different_errors()
        assert result == "success"
        assert call_count == 3

    def test_backoff_increases_delay(self):
        """Test that backoff increases delay between retries"""
        delays = []

        original_sleep = time.sleep
        def mock_sleep(duration):
            delays.append(duration)
            # Don't actually sleep

        with patch('time.sleep', mock_sleep):
            call_count = 0

            @retry_on_failure(max_retries=3, delay=0.1, backoff=2.0)
            def failing_func():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ValueError("Error")
                return "done"

            result = failing_func()
            assert result == "done"

        # Check that delays increase with backoff
        assert len(delays) == 2  # 2 retries needed
        assert delays[0] == 0.1  # First delay
        assert delays[1] == 0.2  # Second delay (backoff * 0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
