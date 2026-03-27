"""Startup coordination for database-backed requests."""

from __future__ import annotations

import asyncio

_db_ready_event = asyncio.Event()
_db_ready_error: Exception | None = None


def reset_db_ready_state() -> None:
    """Mark database startup as in progress."""
    global _db_ready_event, _db_ready_error
    _db_ready_event = asyncio.Event()
    _db_ready_error = None


def mark_db_ready() -> None:
    """Signal that database initialization and migrations are complete."""
    global _db_ready_error
    _db_ready_error = None
    _db_ready_event.set()


def mark_db_failed(exc: Exception) -> None:
    """Signal that database initialization failed."""
    global _db_ready_error
    _db_ready_error = exc
    _db_ready_event.set()


def is_db_ready() -> bool:
    """Return True only when startup completed successfully."""
    return _db_ready_event.is_set() and _db_ready_error is None


async def wait_for_db_ready(timeout: float = 45.0) -> None:
    """Wait for database startup to finish or raise on timeout/failure."""
    if is_db_ready():
        return

    try:
        await asyncio.wait_for(_db_ready_event.wait(), timeout=timeout)
    except TimeoutError as exc:
        raise RuntimeError("Database initialization is still in progress") from exc

    if _db_ready_error is not None:
        raise RuntimeError("Database initialization failed") from _db_ready_error
