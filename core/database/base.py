"""
Database Base Class - Unified CRUD Operations

This module provides a base class for database operations that eliminates
duplicate code across all database modules. It follows the Repository pattern.

Key features:
- Unified query methods (query_one, query_all, execute)
- Automatic connection management with context manager
- Consistent error handling
- Automatic row-to-dict conversion
- Transaction management (commit/rollback)
"""
import psycopg2
from typing import Dict, List, Optional, Any, Union
from contextlib import contextmanager

from .connection import get_connection


# ============================================================================
# Custom Exceptions
# ============================================================================

class DatabaseError(Exception):
    """Base exception for database errors"""
    pass


class DuplicateRecordError(DatabaseError):
    """Raised when trying to insert a duplicate record"""
    pass


class RecordNotFoundError(DatabaseError):
    """Raised when a referenced record doesn't exist"""
    pass


class ValidationError(DatabaseError):
    """Raised when data validation fails"""
    pass


# ============================================================================
# Database Base Class
# ============================================================================

class DatabaseBase:
    """
    Unified database operations base class.

    Provides common CRUD operations that eliminate duplicate code
    across all database modules.

    Usage:
        # Static methods (auto connection management)
        result = DatabaseBase.query_one("SELECT * FROM users WHERE id = %s", (1,))

        # Context manager (manual connection control)
        with DatabaseBase() as db:
            result = db.query_one("SELECT * FROM users WHERE id = %s", (1,))
    """

    def __init__(self, connection=None):
        """
        Initialize with optional connection.

        Args:
            connection: Existing database connection (for transactions)
        """
        self._connection = connection
        self._owns_connection = connection is None

    @property
    def connection(self):
        """Get or create database connection"""
        if self._connection is None:
            self._connection = get_connection()
        return self._connection

    # ========================================================================
    # Static Methods (convenience wrappers)
    # ========================================================================

    @staticmethod
    def query_one(sql: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """
        Execute query and return single row as dictionary.

        Args:
            sql: SQL query string
            params: Query parameters (optional)

        Returns:
            Dict with column names as keys, or None if no result

        Raises:
            DatabaseError: On database errors
        """
        with DatabaseBase() as db:
            return db._query_one(sql, params)

    @staticmethod
    def query_all(sql: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Execute query and return all rows as list of dictionaries.

        Args:
            sql: SQL query string
            params: Query parameters (optional)

        Returns:
            List of dicts with column names as keys

        Raises:
            DatabaseError: On database errors
        """
        with DatabaseBase() as db:
            return db._query_all(sql, params)

    @staticmethod
    def execute(sql: str, params: Optional[tuple] = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE and return affected row count.

        Args:
            sql: SQL statement
            params: Statement parameters (optional)

        Returns:
            Number of affected rows

        Raises:
            DatabaseError: On database errors
            DuplicateRecordError: On integrity constraint violations
            RecordNotFoundError: On foreign key violations
        """
        with DatabaseBase() as db:
            return db._execute(sql, params)

    # ========================================================================
    # Instance Methods (for context manager usage)
    # ========================================================================

    def _query_one(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """Instance method version of query_one"""
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, params or ())
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(cursor, row)
        finally:
            cursor.close()

    def _query_all(self, sql: str, params: Optional[tuple] = None) -> List[Dict]:
        """Instance method version of query_all"""
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, row) for row in rows]
        finally:
            cursor.close()

    def _execute(self, sql: str, params: Optional[tuple] = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE with error handling.

        Returns:
            Number of affected rows
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, params or ())
            self.connection.commit()
            return cursor.rowcount
        except psycopg2.IntegrityError as e:
            self.connection.rollback()
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                raise DuplicateRecordError(str(e))
            elif "foreign key" in str(e).lower():
                raise RecordNotFoundError(str(e))
            raise DatabaseError(f"Integrity error: {e}")
        except Exception as e:
            self.connection.rollback()
            raise DatabaseError(f"Database error: {e}")
        finally:
            cursor.close()

    # ========================================================================
    # Utility Methods
    # ========================================================================

    @staticmethod
    def _row_to_dict(cursor, row: tuple) -> Dict:
        """
        Convert cursor row to dictionary using column names.

        Args:
            cursor: Database cursor with description
            row: Row tuple from fetchone/fetchall

        Returns:
            Dict with column names as keys
        """
        if cursor.description is None:
            return {}
        return {col.name: row[i] for i, col in enumerate(cursor.description)}

    # ========================================================================
    # Context Manager
    # ========================================================================

    def __enter__(self):
        """Enter context manager"""
        if self._owns_connection:
            self._connection = get_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and close connection if we own it"""
        if self._owns_connection and self._connection:
            self._connection.close()
            self._connection = None
        return False


# ============================================================================
# Transaction Helper
# ============================================================================

@contextmanager
def transaction(connection=None):
    """
    Context manager for database transactions.

    Usage:
        with transaction() as conn:
            # Multiple operations on conn
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ...")
            cursor.execute("UPDATE ...")
            # Commits on success, rolls back on error

    Args:
        connection: Existing connection or creates new one

    Yields:
        Database connection
    """
    conn = connection or get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if not connection:
            conn.close()
