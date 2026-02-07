"""
Error Handling Utilities

Provides centralized error logging and handling
to replace silent 'except pass' patterns throughout the codebase.
"""
import logging
from typing import Optional, Callable, Any, Type
from functools import wraps

logger = logging.getLogger(__name__)


def log_and_suppress(
    error_message: str,
    level: str = "warning",
    raise_on: Optional[tuple[Type[Exception], ...]] = None
) -> Callable:
    """
    Decorator to log exceptions instead of silently suppressing them.

    Usage:
        @log_and_suppress("Failed to fetch user data")
        def get_user_safe(user_id: str):
            # This will log the error but not raise
            ...

    Args:
        error_message: Message to log when exception occurs
        level: Logging level ("error", "warning", "info", "debug")
        raise_on: Exception types that should still be raised
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Check if this exception type should still be raised
                if raise_on and isinstance(e, raise_on):
                    raise

                # Log the exception
                log_func = getattr(logger, level, logger.warning)
                log_func(f"{error_message}: {type(e).__name__}: {e}", exc_info=False)

                # Return None or appropriate default
                return None
        return wrapper
    return decorator


def safe_execute(
    fallback_value: Any = None,
    error_message: Optional[str] = None,
    log_level: str = "warning"
) -> Callable:
    """
    Decorator to safely execute functions and return fallback on error.

    Usage:
        @safe_execute(fallback_value=0)
        def get_count():
            # Returns 0 on error instead of raising
            ...

    Args:
        fallback_value: Value to return when exception occurs
        error_message: Optional message to log
        log_level: Logging level for the error
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if error_message:
                    log_func = getattr(logger, log_level, logger.warning)
                    log_func(f"{error_message}: {type(e).__name__}: {e}", exc_info=False)
                return fallback_value
        return wrapper
    return decorator


class ErrorContext:
    """
    Context manager for handling exceptions with logging.

    Usage:
        with ErrorContext("Database operation failed"):
            result = db.query(...)
    """

    def __init__(self, message: str, reraise: bool = False, exception_types: tuple = (Exception,)):
        self.message = message
        self.reraise = reraise
        self.exception_types = exception_types

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # An exception occurred
            if self.reraise or not issubclass(exc_type, self.exception_types):
                logger.error(f"{self.message}: {exc_type.__name__}: {exc_val}", exc_info=True)
            else:
                logger.warning(f"{self.message}: {exc_type.__name__}: {exc_val}")
        # Don't suppress the exception if reraise is True
        return not self.reraise
