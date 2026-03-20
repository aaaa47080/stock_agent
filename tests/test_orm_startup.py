"""Tests for ORM auto-migration and startup integration."""
import inspect
from unittest.mock import patch


class TestAutoMigrateModule:
    """Verify auto_migrate module is properly structured."""

    def test_module_exists(self):
        from core.orm.auto_migrate import auto_migrate
        assert callable(auto_migrate)

    def test_auto_migrate_is_async(self):
        from core.orm.auto_migrate import auto_migrate
        assert inspect.iscoroutinefunction(auto_migrate)

    def test_should_auto_migrate_env_var(self):
        from core.orm.auto_migrate import _should_auto_migrate
        import os
        with patch.dict(os.environ, {"ORM_AUTO_MIGRATE": "true"}, clear=False):
            assert _should_auto_migrate() is True
        with patch.dict(os.environ, {"ORM_AUTO_MIGRATE": "false"}, clear=False):
            assert _should_auto_migrate() is False

    def test_should_auto_migrate_default_dev(self):
        from core.orm.auto_migrate import _should_auto_migrate
        import os
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            assert _should_auto_migrate() is True

    def test_should_auto_migrate_default_prod(self):
        from core.orm.auto_migrate import _should_auto_migrate
        import os
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            assert _should_auto_migrate() is False

    def test_should_auto_migrate_prod_override_true(self):
        from core.orm.auto_migrate import _should_auto_migrate
        import os
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "ORM_AUTO_MIGRATE": "1"}, clear=True):
            assert _should_auto_migrate() is True

    def test_should_auto_migrate_prod_override_no(self):
        from core.orm.auto_migrate import _should_auto_migrate
        import os
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "ORM_AUTO_MIGRATE": "0"}, clear=True):
            assert _should_auto_migrate() is False


class TestAutoMigrateSafety:
    """Verify auto-migrate only adds, never drops or modifies."""

    def test_no_drop_table(self):
        from core.orm.auto_migrate import auto_migrate
        src = inspect.getsource(auto_migrate)
        assert "DROP TABLE" not in src.upper()

    def test_no_drop_column(self):
        from core.orm.auto_migrate import auto_migrate
        src = inspect.getsource(auto_migrate)
        assert "DROP COLUMN" not in src.upper()

    def test_no_alter_column_type(self):
        from core.orm.auto_migrate import _add_missing_columns
        src = inspect.getsource(_add_missing_columns)
        assert "ALTER TABLE" in src
        assert "ADD COLUMN" in src
        # Should NOT have ALTER TABLE ... TYPE (modifying existing columns)
        lines = src.split("\n")
        alter_lines = [line for line in lines if "ALTER TABLE" in line and "ADD COLUMN" not in line]
        assert not alter_lines, f"Found unsafe ALTER TABLE lines: {alter_lines}"

    def test_uses_if_not_exists(self):
        from core.orm.auto_migrate import _add_missing_columns
        src = inspect.getsource(_add_missing_columns)
        assert "IF NOT EXISTS" in src.upper()

    def test_create_table_if_not_exists(self):
        from core.orm.auto_migrate import _create_table_safe
        src = inspect.getsource(_create_table_safe)
        assert "IF NOT EXISTS" in src.upper()


class TestStartupIntegration:
    """Verify auto-migrate is wired into the startup lifecycle."""

    def test_startup_calls_auto_migrate(self):
        from api_server import lifespan
        src = inspect.getsource(lifespan)
        assert "auto_migrate" in src
        assert "core.orm.auto_migrate" in src

    def test_auto_migrate_after_db_init(self):
        from api_server import lifespan
        src = inspect.getsource(lifespan)
        pos_db = src.index("_init_database_background")
        pos_orm = src.index("auto_migrate")
        assert pos_orm > pos_db, "auto_migrate should run after DB init"

    def test_shutdown_closes_async_engine(self):
        from api_server import lifespan
        src = inspect.getsource(lifespan)
        assert "close_async_engine" in src

    def test_shutdown_logs_on_error(self):
        from api_server import lifespan
        src = inspect.getsource(lifespan)
        # Shutdown error handling should use logger.error, not bare except
        assert "logger.error" in src
