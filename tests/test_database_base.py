"""
Tests for database base class (TDD - Red phase)
Tests the unified CRUD operations that will eliminate duplicate database code
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from collections import namedtuple


# Helper function for mocking cursor.description
def mock_cursor_description(cursor, column_names):
    """Helper to mock cursor.description with proper column objects"""
    Column = namedtuple('Column', ['name'])
    cursor.description = [Column(name) for name in column_names]
    return cursor


class TestDatabaseBaseClass:
    """Tests for DatabaseBase unified CRUD operations"""

    def test_query_one_returns_dict(self):
        """Test query_one returns single row as dictionary"""
        # This test will FAIL until we implement DatabaseBase
        from core.database.base import DatabaseBase

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (1, 'test', 'value')
            mock_cursor_description(mock_cursor, ['id', 'name', 'value'])

            result = DatabaseBase.query_one("SELECT * FROM test WHERE id = %s", (1,))

            assert result == {"id": 1, "name": "test", "value": "value"}

    def test_query_one_returns_none_when_no_result(self):
        """Test query_one returns None when no rows found"""
        from core.database.base import DatabaseBase

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None
            mock_cursor_description(mock_cursor, ['id', 'name', 'value'])

            result = DatabaseBase.query_one("SELECT * FROM test WHERE id = %s", (999,))

            assert result is None

    def test_query_all_returns_list_of_dicts(self):
        """Test query_all returns all rows as list of dictionaries"""
        from core.database.base import DatabaseBase

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                (1, 'test1', 'value1'),
                (2, 'test2', 'value2')
            ]
            mock_cursor_description(mock_cursor, ['id', 'name', 'value'])

            results = DatabaseBase.query_all("SELECT * FROM test")

            assert len(results) == 2
            assert results[0] == {"id": 1, "name": "test1", "value": "value1"}
            assert results[1] == {"id": 2, "name": "test2", "value": "value2"}

    def test_execute_insert_and_commit(self):
        """Test execute performs INSERT and commits"""
        from core.database.base import DatabaseBase

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.rowcount = 1

            result = DatabaseBase.execute(
                "INSERT INTO test (name) VALUES (%s) RETURNING id",
                ("test",)
            )

            assert result == 1
            mock_conn.commit.assert_called_once()

    def test_execute_rollback_on_error(self):
        """Test execute rolls back on error"""
        from core.database.base import DatabaseBase

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("DB Error")

            with pytest.raises(Exception):
                DatabaseBase.execute("INSERT INTO test (name) VALUES (%s)", ("test",))

            mock_conn.rollback.assert_called_once()

    def test_context_manager_auto_closes_connection(self):
        """Test DatabaseBase context manager closes connection automatically"""
        from core.database.base import DatabaseBase

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_get_conn.return_value = mock_conn

            with DatabaseBase() as db:
                pass  # Do nothing

            mock_conn.close.assert_called_once()


class TestDatabaseBaseErrorHandling:
    """Tests for unified error handling in DatabaseBase"""

    def test_handles_integrity_error(self):
        """Test proper handling of duplicate key/integrity errors"""
        from core.database.base import DatabaseBase, DuplicateRecordError
        import psycopg2

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = psycopg2.IntegrityError("duplicate key")

            with pytest.raises(DuplicateRecordError):
                DatabaseBase.execute("INSERT INTO test (name) VALUES (%s)", ("test",))

    def test_handles_not_found_error(self):
        """Test proper handling of foreign key not found errors"""
        from core.database.base import DatabaseBase, RecordNotFoundError
        import psycopg2

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = psycopg2.errors.ForeignKeyViolation(
                "foreign key violation"
            )

            with pytest.raises(RecordNotFoundError):
                DatabaseBase.execute("INSERT INTO test (ref) VALUES (%s)", (999,))


class TestDatabaseBaseNamedParameters:
    """Tests for named parameter support in queries"""

    def test_query_one_with_named_params(self):
        """Test query_one with named parameters"""
        from core.database.base import DatabaseBase

        with patch('core.database.base.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (1, 'test')
            mock_cursor_description(mock_cursor, ['id', 'name'])

            result = DatabaseBase.query_one(
                "SELECT * FROM test WHERE id = :id AND name = :name",
                {"id": 1, "name": "test"}
            )

            assert result is not None
            # Verify execute was called with positional params
            mock_cursor.execute.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
