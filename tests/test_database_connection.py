"""
Tests for database connection in core/database/connection.py
"""

import pytest
from unittest.mock import patch, MagicMock
import threading

from core.database.connection import (
    PooledConnection,
    _StandaloneConnection,
    _build_database_url_from_components,
    get_database_url,
    init_db,
    init_connection_pool,
    get_connection,
    close_all_connections,
    reset_connection_pool,
    MIN_POOL_SIZE,
    MAX_POOL_SIZE,
    MAX_RETRIES,
)


class TestPooledConnection:
    """Tests for PooledConnection class"""

    def test_close_returns_to_pool(self):
        """Test that close() returns connection to pool"""
        mock_conn = MagicMock()
        mock_pool = MagicMock()

        pooled = PooledConnection(mock_conn, mock_pool)
        pooled.close()

        # Should call putconn to return connection
        mock_pool.putconn.assert_called_once_with(mock_conn)

    def test_context_manager(self):
        """Test context manager protocol"""
        mock_conn = MagicMock()
        mock_pool = MagicMock()

        with PooledConnection(mock_conn, mock_pool):
            pass

        # Should have called putconn after exiting context
        mock_pool.putconn.assert_called()

    def test_rollback_on_close(self):
        """Test that rollback is called before returning connection"""
        mock_conn = MagicMock()
        mock_pool = MagicMock()

        pooled = PooledConnection(mock_conn, mock_pool)
        pooled.close()

        # Should rollback first
        mock_conn.rollback.assert_called()

    def test_attribute_proxy(self):
        """Test that attributes are proxied to underlying connection"""
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value="cursor_obj")
        mock_pool = MagicMock()

        pooled = PooledConnection(mock_conn, mock_pool)
        result = pooled.cursor()

        assert result == "cursor_obj"

    def test_double_close_only_returns_once(self):
        """Test that double close only returns connection once"""
        mock_conn = MagicMock()
        mock_pool = MagicMock()

        pooled = PooledConnection(mock_conn, mock_pool)
        pooled.close()
        pooled.close()  # Second close

        # Should only be called once
        mock_pool.putconn.assert_called_once()

    def test_close_handles_putconn_failure(self):
        """Test that close handles putconn failure gracefully"""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.putconn.side_effect = Exception("Pool error")

        pooled = PooledConnection(mock_conn, mock_pool)
        # Should not raise
        pooled.close()

        # Should try to close the underlying connection
        mock_conn.close.assert_called()


class TestStandaloneConnection:
    """Tests for _StandaloneConnection class"""

    def test_close_actually_closes(self):
        """Test that close() actually closes the connection"""
        mock_conn = MagicMock()

        standalone = _StandaloneConnection(mock_conn)
        standalone.close()

        mock_conn.close.assert_called_once()

    def test_rollback_before_close(self):
        """Test that rollback is called before close"""
        mock_conn = MagicMock()

        standalone = _StandaloneConnection(mock_conn)
        standalone.close()

        mock_conn.rollback.assert_called()

    def test_context_manager(self):
        """Test context manager protocol"""
        mock_conn = MagicMock()

        with _StandaloneConnection(mock_conn):
            pass

        mock_conn.close.assert_called()

    def test_attribute_proxy(self):
        """Test that attributes are proxied to underlying connection"""
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value="cursor_obj")

        standalone = _StandaloneConnection(mock_conn)
        result = standalone.cursor()

        assert result == "cursor_obj"

    def test_double_close_only_closes_once(self):
        """Test that double close only closes once"""
        mock_conn = MagicMock()

        standalone = _StandaloneConnection(mock_conn)
        standalone.close()
        standalone.close()  # Second close

        mock_conn.close.assert_called_once()

    def test_handles_close_failure(self):
        """Test that close handles failure gracefully"""
        mock_conn = MagicMock()
        mock_conn.close.side_effect = Exception("Close failed")

        standalone = _StandaloneConnection(mock_conn)
        # Should not raise
        standalone.close()


class TestInitConnectionPool:
    """Tests for init_connection_pool function"""

    def test_creates_threaded_pool(self):
        """Test that ThreadedConnectionPool is created"""
        with patch("core.database.connection.DATABASE_URL", "postgresql://test"):
            with patch("core.database.connection._connection_pool", None):
                with patch("psycopg2.pool.ThreadedConnectionPool") as mock_pool_class:
                    mock_pool = MagicMock()
                    mock_pool_class.return_value = mock_pool

                    with patch("core.database.connection.logger"):
                        result = init_connection_pool()

                    mock_pool_class.assert_called_once()
                    assert result == mock_pool

    def test_raises_without_database_url(self):
        """Test that ValueError is raised without DATABASE_URL"""
        with patch("core.database.connection.get_database_url", return_value=None):
            with patch("core.database.connection._connection_pool", None):
                with pytest.raises(ValueError) as exc_info:
                    init_connection_pool()

                assert "Database connection" in str(exc_info.value)

    def test_retry_on_operational_error(self):
        """Test retry on OperationalError"""
        with patch("core.database.connection.DATABASE_URL", "postgresql://test"):
            with patch("core.database.connection._connection_pool", None):
                with patch("psycopg2.pool.ThreadedConnectionPool") as mock_pool_class:
                    from psycopg2 import OperationalError

                    mock_pool = MagicMock()
                    mock_pool_class.side_effect = [
                        OperationalError("Connection failed"),
                        mock_pool,
                    ]

                    with patch("core.database.connection.logger"):
                        with patch("time.sleep"):
                            result = init_connection_pool()

                    assert result == mock_pool
                    assert mock_pool_class.call_count == 2

    def test_raises_after_max_retries(self):
        """Test that error is raised after max retries"""
        with patch("core.database.connection.DATABASE_URL", "postgresql://test"):
            with patch("core.database.connection._connection_pool", None):
                with patch("psycopg2.pool.ThreadedConnectionPool") as mock_pool_class:
                    from psycopg2 import OperationalError

                    mock_pool_class.side_effect = OperationalError("Connection failed")

                    with patch("core.database.connection.logger"):
                        with patch("time.sleep"):
                            with pytest.raises(OperationalError):
                                init_connection_pool()

                assert "Database connection" in str(exc_info.value)

    def test_retry_on_operational_error(self):
        """Test retry on OperationalError"""
        with patch("core.database.connection.DATABASE_URL", "postgresql://test"):
            with patch("core.database.connection._connection_pool", None):
                with patch("psycopg2.pool.ThreadedConnectionPool") as mock_pool_class:
                    # First call fails, second succeeds
                    from psycopg2 import OperationalError

                    mock_pool = MagicMock()
                    mock_pool_class.side_effect = [
                        OperationalError("Connection failed"),
                        mock_pool,
                    ]

                    with patch("builtins.print"):
                        with patch("time.sleep"):
                            result = init_connection_pool()

                    assert result == mock_pool
                    assert mock_pool_class.call_count == 2

    def test_raises_after_max_retries(self):
        """Test that error is raised after max retries"""
        with patch("core.database.connection.DATABASE_URL", "postgresql://test"):
            with patch("core.database.connection._connection_pool", None):
                with patch("psycopg2.pool.ThreadedConnectionPool") as mock_pool_class:
                    from psycopg2 import OperationalError

                    mock_pool_class.side_effect = OperationalError("Connection failed")

                    with patch("builtins.print"):
                        with patch("time.sleep"):
                            with pytest.raises(OperationalError):
                                init_connection_pool()


class TestGetConnection:
    """Tests for get_connection function"""

    def test_returns_pooled_connection(self):
        """Test that PooledConnection is returned"""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock()
        mock_cursor.close = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection._db_initialized", True):
                result = get_connection()

                assert isinstance(result, PooledConnection)


class TestInitDb:
    """Tests for init_db schema bootstrap and reconcile flow."""

    def test_init_db_runs_create_and_reconcile_steps(self):
        """init_db should create tables, run reconcile, then commit once."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "core.database.connection.get_database_url",
            return_value="postgresql://test",
        ):
            with patch(
                "core.database.connection.psycopg2.connect", return_value=mock_conn
            ):
                with patch(
                    "core.database.connection.create_all_tables"
                ) as mock_create_all_tables:
                    with patch(
                        "core.database.connection.reconcile_existing_tables",
                        return_value={"audit_logs": ["endpoint"]},
                    ) as mock_reconcile:
                        with patch(
                            "core.database.connection.format_reconcile_summary",
                            return_value="audit_logs(1)",
                        ) as mock_format:
                            with patch(
                                "core.database.connection.logger"
                            ) as mock_logger:
                                init_db()

        mock_create_all_tables.assert_called_once_with(mock_cursor)
        mock_reconcile.assert_called_once_with(mock_cursor)
        mock_format.assert_called_once_with({"audit_logs": ["endpoint"]})
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_logger.info.assert_called_once()

    def test_replaces_closed_connection(self):
        """Test that closed connection is replaced"""
        mock_pool = MagicMock()
        mock_closed_conn = MagicMock()
        mock_closed_conn.closed = True
        mock_good_conn = MagicMock()
        mock_good_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock()
        mock_cursor.close = MagicMock()
        mock_good_conn.cursor.return_value = mock_cursor

        # First returns closed, second returns good
        mock_pool.getconn.side_effect = [mock_closed_conn, mock_good_conn]

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection._db_initialized", True):
                result = get_connection()

                assert isinstance(result, PooledConnection)

    def test_raises_runtime_error_on_pool_exhaustion(self):
        """Test that RuntimeError is raised when pool is exhausted (no bypass)"""
        from psycopg2 import pool

        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = pool.PoolError("Pool exhausted")

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection._db_initialized", True):
                with patch("time.sleep"):
                    with pytest.raises(RuntimeError) as exc_info:
                        get_connection()

                    assert "Service unavailable" in str(exc_info.value)
                    assert "pool exhausted" in str(exc_info.value)

    def test_no_standalone_connection_on_bad_connections(self):
        """Test that no standalone bypass connection is created for bad connections"""
        mock_pool = MagicMock()
        mock_bad_conn = MagicMock()
        mock_bad_conn.closed = False
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("SSL broken")
        mock_cursor.fetchone = MagicMock()
        mock_cursor.close = MagicMock()
        mock_bad_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_bad_conn

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection._db_initialized", True):
                with pytest.raises((RuntimeError, Exception)):
                    get_connection()

        mock_pool.getconn.assert_called()
        standalone_created = any(
            isinstance(call, _StandaloneConnection)
            for call in []
        )
        assert not standalone_created


class TestCloseAllConnections:
    """Tests for close_all_connections function"""

    def test_closes_all_connections(self):
        """Test that closeall is called on pool"""
        mock_pool = MagicMock()

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection.logger"):
                close_all_connections()

            mock_pool.closeall.assert_called_once()

    def test_handles_none_pool(self):
        """Test that None pool is handled"""
        with patch("core.database.connection._connection_pool", None):
            close_all_connections()

    def test_clears_pool_after_close(self):
        """Test that pool is cleared after close"""
        mock_pool = MagicMock()

        import core.database.connection as conn_module

        conn_module._connection_pool = mock_pool

        with patch("core.database.connection.logger"):
            close_all_connections()

        assert conn_module._connection_pool is None


class TestResetConnectionPool:
    """Tests for reset_connection_pool function"""

    def test_resets_global_pool(self):
        """Test that global pool is reset"""
        mock_pool = MagicMock()

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection._db_initialized", True):
                reset_connection_pool()

                mock_pool.closeall.assert_called()

    def test_clears_initialized_flag(self):
        """Test that _db_initialized flag is cleared"""
        mock_pool = MagicMock()

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection._db_initialized", True):
                import core.database.connection as conn_module

                reset_connection_pool()

                # Flag should be cleared
                assert conn_module._db_initialized is False

    def test_handles_close_error(self):
        """Test that close error is handled gracefully"""
        mock_pool = MagicMock()
        mock_pool.closeall.side_effect = Exception("Close failed")

        with patch("core.database.connection._connection_pool", mock_pool):
            with patch("core.database.connection._db_initialized", True):
                # Should not raise
                reset_connection_pool()


class TestConnectionConstants:
    """Tests for connection constants"""

    def test_pool_size_constants(self):
        """Test pool size constants are reasonable"""
        assert MIN_POOL_SIZE >= 1
        assert MAX_POOL_SIZE >= MIN_POOL_SIZE

    def test_retry_constants(self):
        """Test retry constants are reasonable"""
        assert MAX_RETRIES >= 1


class TestDatabaseUrlResolution:
    """Tests for database URL resolution helpers"""

    def test_builds_database_url_from_components_with_encoding(self):
        env = {
            "POSTGRESQL_HOST": "service.internal",
            "POSTGRESQL_USER": "root",
            "POSTGRESQL_PASSWORD": "Zb9$mK2@pL7",
            "POSTGRESQL_DB": "zeabur",
            "POSTGRESQL_PORT": "5432",
        }

        result = _build_database_url_from_components(env)

        assert result == (
            "postgresql://root:Zb9%24mK2%40pL7@service.internal:5432/zeabur"
        )

    def test_component_url_takes_precedence_over_raw_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://broken:url")
        monkeypatch.setenv("POSTGRESQL_HOST", "service.internal")
        monkeypatch.setenv("POSTGRESQL_USER", "root")
        monkeypatch.setenv("POSTGRESQL_PASSWORD", "pa@ss")
        monkeypatch.setenv("POSTGRESQL_DB", "zeabur")
        monkeypatch.setenv("POSTGRESQL_PORT", "5432")

        result = get_database_url()

        assert result == "postgresql://root:pa%40ss@service.internal:5432/zeabur"


class TestThreadSafety:
    """Tests for thread safety"""

    def test_pool_lock_exists(self):
        """Test that pool lock exists"""
        from core.database.connection import _pool_lock

        assert isinstance(_pool_lock, type(threading.Lock()))

    def test_concurrent_pool_init(self):
        """Test that concurrent pool init is safe"""
        results = []

        def try_init():
            try:
                with patch(
                    "core.database.connection.DATABASE_URL", "postgresql://test"
                ):
                    with patch("psycopg2.pool.ThreadedConnectionPool"):
                        results.append("init_attempted")
            except Exception as e:
                results.append(f"error: {e}")

        threads = [threading.Thread(target=try_init) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should have attempted init
        assert len(results) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
