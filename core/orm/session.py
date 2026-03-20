"""
SQLAlchemy 2.0 Async engine and session factory.

Provides a shared async engine and sessionmaker that can be used
throughout the application. The engine is lazily initialized on first use.

Usage::

    from core.orm.session import get_async_session

    async with get_async_session() as session:
        result = await session.execute(select(User).where(User.user_id == "uid"))
        user = result.scalar_one_or_none()
"""
from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import quote

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

_async_engine = None
_async_session_factory = None


def _resolve_async_url() -> str | None:
    """Build an async PostgreSQL URL from environment variables."""
    host = os.getenv("POSTGRESQL_HOST")
    user = os.getenv("POSTGRESQL_USER")
    password = os.getenv("POSTGRESQL_PASSWORD")
    db_name = os.getenv("POSTGRESQL_DB") or os.getenv("POSTGRES_DB")
    port = os.getenv("POSTGRESQL_PORT", "5432")

    if not all([host, user, password, db_name]):
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            url = url.replace("sslmode=require", "ssl=require", 1)
            url = url.replace("&channel_binding=require", "", 1)
            return url
        return None

    encoded_user = quote(str(user), safe="")
    encoded_password = quote(str(password), safe="")
    encoded_db = quote(str(db_name), safe="")

    return (
        f"postgresql+asyncpg://{encoded_user}:{encoded_password}"
        f"@{host}:{port}/{encoded_db}"
    )


def get_engine():
    """Return the global async engine, creating it if needed."""
    global _async_engine
    if _async_engine is None:
        url = _resolve_async_url()
        if not url:
            raise RuntimeError(
                "Cannot create async engine: no DATABASE_URL or "
                "POSTGRESQL_* variables set"
            )
        pool_size = int(os.getenv("DB_MAX_POOL_SIZE", "10"))
        _async_engine = create_async_engine(
            url,
            pool_size=pool_size,
            max_overflow=pool_size,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        logger.info("Async SQLAlchemy engine created (pool_size=%d)", pool_size)
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_async_engine():
    """Dispose the async engine (call on shutdown)."""
    global _async_engine, _async_session_factory
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
        logger.info("Async SQLAlchemy engine disposed")


@asynccontextmanager
async def using_session(session: AsyncSession | None = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a session for repo use.

    If *session* is provided (e.g. from a FastAPI dependency), use it
    directly without committing or closing — the caller manages the
    lifecycle.  Otherwise create, commit, and close a new session.
    """
    if session is not None:
        yield session
    else:
        factory = get_session_factory()
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise
