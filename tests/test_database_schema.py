"""Tests for schema create/reconcile helpers."""

from unittest.mock import MagicMock

from core.database.schema import (
    format_reconcile_summary,
    reconcile_existing_tables,
    reconcile_payment_tables,
)


class TestSchemaReconcile:
    """Tests for safe schema reconciliation."""

    def test_reconcile_existing_tables_runs_key_table_steps(self):
        """Reconcile should check the legacy tables we support at startup."""
        mock_cursor = MagicMock()

        summary = reconcile_existing_tables(mock_cursor)

        assert "users" in summary
        assert "audit_logs" in summary
        assert "scam_report_comments" in summary
        assert "tools_catalog" in summary
        assert "payment_tables" in summary
        assert any(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role" in call.args[0]
            for call in mock_cursor.execute.call_args_list
        )
        assert any(
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS endpoint" in call.args[0]
            for call in mock_cursor.execute.call_args_list
        )
        assert any(
            "ALTER TABLE scam_report_comments DROP COLUMN IF EXISTS attachment_url"
            in call.args[0]
            for call in mock_cursor.execute.call_args_list
        )
        assert any(
            "UPDATE audit_logs SET endpoint = COALESCE(endpoint, 'system://legacy')"
            in call.args[0]
            for call in mock_cursor.execute.call_args_list
        )

    def test_reconcile_existing_tables_adds_tx_hash_unique(self):
        """Reconcile should add UNIQUE constraints on tx_hash columns."""
        mock_cursor = MagicMock()

        reconcile_existing_tables(mock_cursor)

        sql_calls = [call.args[0] for call in mock_cursor.execute.call_args_list]
        assert any(
            "idx_membership_payments_tx_hash" in sql and "UNIQUE" in sql
            for sql in sql_calls
        )
        assert any(
            "idx_tips_tx_hash" in sql and "UNIQUE" in sql
            for sql in sql_calls
        )
        assert any(
            "idx_posts_payment_tx_hash" in sql and "UNIQUE" in sql
            for sql in sql_calls
        )
        assert any(
            "payment_tx_hash IS NOT NULL" in sql
            for sql in sql_calls
        )

    def test_reconcile_payment_tables_success(self):
        """reconcile_payment_tables returns checked items on success."""
        mock_cursor = MagicMock()

        result = reconcile_payment_tables(mock_cursor)

        assert "membership_payments.tx_hash_unique" in result
        assert "tips.tx_hash_unique" in result
        assert "posts.payment_tx_hash_unique_partial" in result
        assert mock_cursor.execute.call_count == 3

    def test_reconcile_payment_tables_handles_failure_gracefully(self):
        """reconcile_payment_tables should continue even if one index fails."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = [
            Exception("duplicate key"),
            None,
            None,
        ]

        result = reconcile_payment_tables(mock_cursor)

        assert "membership_payments.tx_hash_unique" not in result
        assert "tips.tx_hash_unique" in result
        assert "posts.payment_tx_hash_unique_partial" in result
        assert mock_cursor.execute.call_count == 3

    def test_format_reconcile_summary_compacts_counts(self):
        """Startup logging should format reconcile counts in a compact form."""
        summary = {
            "users": ["role", "is_active"],
            "audit_logs": ["endpoint"],
            "tools_catalog": [],
            "payment_tables": ["membership_payments.tx_hash_unique"],
        }

        assert format_reconcile_summary(summary) == "users(2), audit_logs(1), payment_tables(1)"


class TestSchemaDDL:
    """Tests for DDL statements in CREATE TABLE definitions."""

    def test_membership_payments_tx_hash_has_unique(self):
        """membership_payments CREATE TABLE should include UNIQUE on tx_hash."""
        from core.database.schema import create_user_tables

        mock_cursor = MagicMock()
        create_user_tables(mock_cursor)

        sql_calls = [call.args[0] for call in mock_cursor.execute.call_args_list]
        ddl = [s for s in sql_calls if "membership_payments" in s and "CREATE TABLE" in s]
        assert len(ddl) == 1
        assert "tx_hash" in ddl[0]
        assert "UNIQUE" in ddl[0]

    def test_tips_tx_hash_has_unique(self):
        """tips CREATE TABLE should include UNIQUE on tx_hash."""
        from core.database.schema import create_forum_tables

        mock_cursor = MagicMock()
        create_forum_tables(mock_cursor)

        sql_calls = [call.args[0] for call in mock_cursor.execute.call_args_list]
        ddl = [s for s in sql_calls if "CREATE TABLE IF NOT EXISTS tips" in s]
        assert len(ddl) == 1
        assert "tx_hash" in ddl[0]
        assert "UNIQUE" in ddl[0]

    def test_posts_payment_tx_hash_partial_unique_index(self):
        """posts should have a partial unique index on payment_tx_hash."""
        from core.database.schema import create_indexes

        mock_cursor = MagicMock()
        create_indexes(mock_cursor)

        sql_calls = [call.args[0] for call in mock_cursor.execute.call_args_list]
        assert any(
            "idx_posts_payment_tx_hash" in sql
            and "UNIQUE" in sql
            and "payment_tx_hash IS NOT NULL" in sql
            for sql in sql_calls
        )
