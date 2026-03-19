"""Tests for schema create/reconcile helpers."""

from unittest.mock import MagicMock

from core.database.schema import format_reconcile_summary, reconcile_existing_tables


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

    def test_format_reconcile_summary_compacts_counts(self):
        """Startup logging should format reconcile counts in a compact form."""
        summary = {
            "users": ["role", "is_active"],
            "audit_logs": ["endpoint"],
            "tools_catalog": [],
        }

        assert format_reconcile_summary(summary) == "users(2), audit_logs(1)"
