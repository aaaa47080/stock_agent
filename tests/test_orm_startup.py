"""Tests for ORM migration and startup integration.

The legacy ``core.orm.auto_migrate`` module has been replaced by Alembic.
These tests now verify that the old module is gone and that the new
Alembic-based migration is wired into the startup lifecycle.
"""

import pytest


def _read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestAutoMigrateModule:
    """Verify the old auto_migrate module has been replaced by Alembic."""

    def test_module_does_not_exist(self):
        """core.orm.auto_migrate should no longer be importable."""
        with pytest.raises(ImportError):
            import core.orm.auto_migrate  # noqa: F401

    def test_alembic_config_exists(self):
        """alembic.ini should exist at the project root."""
        import os

        assert os.path.isfile("alembic.ini")

    def test_alembic_env_file_exists(self):
        """alembic/env.py should exist."""
        import os

        assert os.path.isfile("alembic/env.py")


class TestAutoMigrateSafety:
    """Verify Alembic migration is properly configured instead of raw SQL auto_migrate."""

    def test_alembic_upgrade_head_in_lifespan(self):
        """The lifespan function should call alembic upgrade to head."""
        src = _read_file("api/lifespan.py")
        assert "alembic" in src.lower()
        assert "upgrade" in src.lower()

    def test_no_drop_table_in_lifespan(self):
        """The lifespan function should not contain raw DROP TABLE statements."""
        src = _read_file("api/lifespan.py")
        assert "DROP TABLE" not in src.upper()

    def test_no_alter_column_in_lifespan(self):
        """The lifespan function should not contain raw ALTER TABLE statements for columns."""
        src = _read_file("api/lifespan.py")
        assert "ALTER TABLE" not in src.upper()


class TestStartupIntegration:
    """Verify Alembic migration is wired into the startup lifecycle."""

    def test_startup_calls_alembic_upgrade(self):
        src = _read_file("api/lifespan.py")
        assert "alembic" in src.lower()
        assert "upgrade" in src.lower()
        assert "head" in src.lower()

    def test_alembic_after_db_init(self):
        src = _read_file("api/lifespan.py")
        pos_db = src.index("_init_database_background")
        pos_orm = src.index("upgrade")
        assert pos_orm > pos_db, "alembic upgrade should run after DB init"

    def test_shutdown_closes_async_engine(self):
        src = _read_file("api/lifespan.py")
        assert "close_async_engine" in src

    def test_shutdown_logs_on_error(self):
        src = _read_file("api/lifespan.py")
        # Shutdown error handling should use logger.error, not bare except
        assert "logger.error" in src
