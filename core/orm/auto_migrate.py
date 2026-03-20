"""
Enterprise-grade auto-migration: safely syncs ORM models to the database.

Rules:
- CREATE TABLE IF NOT EXISTS for new tables
- ALTER TABLE ADD COLUMN IF NOT EXISTS for missing columns
- Never DROP tables, columns, or indexes
- Never modify existing column types (use reconcile for that)
- Controlled by ORM_AUTO_MIGRATE env var (default: true in dev, false in prod)

Usage::

    from core.orm.auto_migrate import auto_migrate

    changes = await auto_migrate(engine)
    # changes = {"tables_created": [...], "columns_added": [...]}
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.schema import CreateTable

from .models import Base

logger = logging.getLogger(__name__)


def _should_auto_migrate() -> bool:
    """Check if auto-migration is enabled via environment variable."""
    env_val = os.getenv("ORM_AUTO_MIGRATE", "").lower()
    if env_val in ("0", "false", "no", "off"):
        return False
    if env_val in ("1", "true", "yes", "on"):
        return True
    return os.getenv("ENVIRONMENT", "development").lower() not in ("production", "prod")


def _get_db_tables(inspector) -> set[str]:
    """Synchronous: get existing table names from the database."""
    return set(inspector.get_table_names())


def _get_db_columns(inspector, table_name: str) -> set[str]:
    """Synchronous: get existing column names for a table."""
    return {c["name"] for c in inspector.get_columns(table_name)}


async def auto_migrate(engine: AsyncEngine) -> dict[str, list[str]]:
    """
    Safely sync ORM models to the database.

    Returns a dict with:
      - "tables_created": list of table names that were created
      - "columns_added": list of "table.column" strings that were added
    """
    if not _should_auto_migrate():
        logger.info(
            "ORM auto-migration disabled (ORM_AUTO_MIGRATE=%s)",
            os.getenv("ORM_AUTO_MIGRATE", "not set"),
        )
        return {"tables_created": [], "columns_added": []}

    tables_created: list[str] = []
    columns_added: list[str] = []

    async with engine.connect() as conn:

        def _inspect_tables(connection):
            from sqlalchemy import inspect as sa_inspect

            insp = sa_inspect(connection)
            return _get_db_tables(insp)

        db_tables = await conn.run_sync(_inspect_tables)

        for table in Base.metadata.sorted_tables:
            if table.name not in db_tables:
                await _create_table_safe(conn, table)
                tables_created.append(table.name)
                logger.info("ORM auto-migrate: created table '%s'", table.name)
            else:
                added = await _add_missing_columns(conn, table.name, table)
                if added:
                    logger.info(
                        "ORM auto-migrate: added columns to '%s': %s", table.name, added
                    )
                columns_added.extend(added)

        await conn.commit()

    total = len(tables_created) + len(columns_added)
    if total > 0:
        logger.info(
            "ORM auto-migration complete: %d tables created, %d columns added",
            len(tables_created),
            len(columns_added),
        )
    else:
        logger.info("ORM auto-migrate: schema is up to date")

    return {"tables_created": tables_created, "columns_added": columns_added}


async def _create_table_safe(conn, table):
    """Create a table using IF NOT EXISTS pattern."""
    ddl = CreateTable(table.name, table.metadata, *(table.indexes or []))
    raw_ddl = ddl.compile(dialect=conn.dialect)
    raw_str = raw_ddl.string if hasattr(raw_ddl, "string") else str(raw_ddl)
    raw_str = raw_str.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
    await conn.execute(text(raw_str))


async def _add_missing_columns(conn, table_name: str, table) -> list[str]:
    """Add columns that exist in the ORM model but not in the database."""
    added: list[str] = []

    def _inspect_columns(connection):
        from sqlalchemy import inspect as sa_inspect

        insp = sa_inspect(connection)
        try:
            return _get_db_columns(insp, table_name)
        except Exception:
            logger.warning(
                "Cannot inspect table '%s', skipping column check", table_name
            )
            return None

    db_columns = await conn.run_sync(_inspect_columns)
    if db_columns is None:
        return added

    for column in table.columns:
        if column.name not in db_columns:
            col_type = column.type.compile(dialect=conn.dialect)
            nullable = "NULL" if column.nullable else "NOT NULL"
            default = ""
            if column.server_default is not None:
                default = f" DEFAULT {column.server_default.arg}"
            elif column.default is not None:
                default = " DEFAULT NULL"

            sql = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column.name} {col_type} {nullable}{default}"
            await conn.execute(text(sql))
            added.append(f"{table_name}.{column.name}")

    return added
