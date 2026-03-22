"""
Database Bridge — Unified access layer for the dual-DB migration.

This module provides utilities to bridge the legacy psycopg2 sync layer
(`core.database.*`) and the newer SQLAlchemy async layer (`core.orm.*`).

**Current architecture (dual-DB):**

    ┌─────────────────────────────────────┐
    │          Application Code           │
    └──────────┬──────────────┬───────────┘
               │              │
    ┌──────────▼──────┐  ┌───▼────────────┐
    │ core.database/  │  │   core/orm/     │
    │  (psycopg2)     │  │ (SQLAlchemy)    │
    │  sync, raw SQL  │  │  async, ORM     │
    └────────┬────────┘  └───────┬────────┘
             │                   │
    ┌────────▼───────────────────▼────────┐
    │           PostgreSQL 16             │
    └────────────────────────────────────┘

Both layers maintain their own connection pools, which doubles resource
consumption and adds operational complexity.

**Migration Roadmap:**

    Phase 1 — Bridge (this file, NOW)
        • ``run_sync_in_thread()``: run existing sync DB calls from async code
          without blocking the event loop.
        • ``get_async_db()``: convenience async context manager for simple
          queries via the ORM layer.
        • No changes to existing code.

    Phase 2 — Incremental Migration
        • Migrate one module at a time (e.g. user → friends → forum …).
        • Each module's route layer switches from ``core.database.xxx`` to
          ``core.orm.xxx_repo``.
        • ``run_sync_in_thread()`` serves as a stop-gap for modules not yet
          migrated.
        • Every migrated module removes its ``core.database/`` counterpart
          and drops one pool consumer.

    Phase 3 — Single Pool
        • Once all modules use ``core.orm``, remove the psycopg2 pool entirely
          (``core.database/connection.py`` ThreadedConnectionPool).
        • Keep ``core.database/schema.py`` for DDL / migrations only.
        • Optionally replace raw-SQL helpers in ``core.database/base.py``
          with thin ORM wrappers if any ad-hoc queries remain.

    Phase 4 — Cleanup
        • Delete ``core/database/{user,forum,friends,…}.py``.
        • Consolidate ``__init__.py`` exports.
        • Archive ``bridge.py`` (or keep as a thin ``run_sync_in_thread``
          utility for edge cases).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, TypeVar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# 1. Run sync DB functions in a thread pool
# ---------------------------------------------------------------------------

_default_executor = None


def _get_executor() -> asyncio.Executor:
    """Return (or create) a dedicated thread-pool executor for sync DB calls."""
    global _default_executor
    if _default_executor is None:
        _default_executor = asyncio.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="db-sync-"
        )
    return _default_executor


async def run_sync_in_thread(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Execute a synchronous DB function in a worker thread.

    This allows calling the legacy ``core.database.*`` functions from async
    code without blocking the main event loop.  The function should be
    self-contained (it obtains and closes its own connection internally).

    Args:
        func: A synchronous callable that performs DB work.
        *args: Positional arguments forwarded to *func*.
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        Whatever *func* returns.

    Raises:
        Exception: Any exception raised by *func* is re-raised in the caller.

    Example::

        from core.database import get_user_by_id
        from core.database.bridge import run_sync_in_thread

        async def my_async_endpoint(user_id: str):
            user = await run_sync_in_thread(get_user_by_id, user_id)
            return user
    """
    loop = asyncio.get_running_loop()
    if kwargs:
        func = partial(func, *args, **kwargs)
        return await loop.run_in_executor(_get_executor(), func)
    return await loop.run_in_executor(_get_executor(), func, *args)


# ---------------------------------------------------------------------------
# 2. Convenience async context manager for simple ORM queries
# ---------------------------------------------------------------------------


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a short-lived SQLAlchemy session.

    Internally delegates to :func:`core.orm.session.get_async_session`.
    The session is automatically committed on success and rolled back on
    error.

    This is intended for simple, standalone queries.  For request-scoped
    sessions (e.g. inside a FastAPI dependency), use
    ``core.orm.get_async_session`` directly so that multiple operations
    share the same transaction.

    Example::

        from core.database.bridge import get_async_db
        from sqlalchemy import select
        from core.orm.models import User

        async def fetch_user(uid: str):
            async with get_async_db() as session:
                result = await session.execute(
                    select(User).where(User.user_id == uid)
                )
                return result.scalar_one_or_none()
    """
    from core.orm.session import get_async_session

    async with get_async_session() as session:
        yield session
