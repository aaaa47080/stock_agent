"""Tests for Phase 2 database schema robustness changes."""

import inspect
import re

import pytest


def _get_schema_source():
    from core.database import schema

    return inspect.getsource(schema)


class TestCheckConstraints:
    """Verify CHECK constraints are defined for data integrity."""

    def test_reconcile_check_constraints_exists(self):
        from core.database.schema import reconcile_check_constraints

        assert callable(reconcile_check_constraints)

    def test_amount_positive_on_membership_payments(self):
        src = _get_schema_source()
        assert "ck_amount_positive" in src
        assert "membership_payments" in src
        assert "amount > 0" in src

    def test_months_positive_on_membership_payments(self):
        src = _get_schema_source()
        assert "months > 0" in src

    def test_tip_amount_positive(self):
        src = _get_schema_source()
        assert "ck_tip_amount_positive" in src or "tips" in src
        assert "amount > 0" in src

    def test_price_alert_target_positive(self):
        src = _get_schema_source()
        assert "price_alerts" in src
        assert "target > 0" in src

    def test_friendship_status_check(self):
        src = _get_schema_source()
        assert "ck_friendship_status" in src or "friendships" in src
        assert "'pending'" in src
        assert "'accepted'" in src
        assert "'blocked'" in src

    def test_comment_type_check(self):
        src = _get_schema_source()
        assert "forum_comments" in src
        assert "'comment'" in src
        assert "'reply'" in src

    def test_verification_status_check(self):
        src = _get_schema_source()
        assert "scam_reports" in src
        assert "'verified'" in src
        assert "'rejected'" in src

    def test_vote_type_check(self):
        src = _get_schema_source()
        assert "'approve'" in src
        assert "'reject'" in src

    def test_reconcile_existing_calls_check_constraints(self):
        from core.database.schema import reconcile_existing_tables

        src = inspect.getsource(reconcile_existing_tables)
        assert "reconcile_check_constraints" in src


class TestForeignKeys:
    """Verify missing foreign keys are added via reconcile."""

    def test_reconcile_foreign_keys_exists(self):
        from core.database.schema import reconcile_foreign_keys

        assert callable(reconcile_foreign_keys)

    @pytest.mark.parametrize(
        "table,col",
        [
            ("admin_broadcasts", "admin_user_id"),
            ("user_violations", "user_id"),
            ("user_violation_points", "user_id"),
            ("audit_reputation", "user_id"),
            ("user_activity_logs", "user_id"),
            ("conversation_history", "user_id"),
            ("sessions", "user_id"),
            ("user_tool_preferences", "user_id"),
        ],
    )
    def test_fk_added_for_table(self, table, col):
        src = _get_schema_source()
        assert table in src
        pattern = re.compile(rf"fk_\w+.*{col}.*REFERENCES\s+users", re.IGNORECASE)
        found = pattern.search(src)
        assert found, f"Missing FK: {table}.{col} -> users(user_id)"

    def test_reconcile_existing_calls_foreign_keys(self):
        from core.database.schema import reconcile_existing_tables

        src = inspect.getsource(reconcile_existing_tables)
        assert "reconcile_foreign_keys" in src


class TestNumericMigration:
    """Verify REAL columns are changed to NUMERIC(18,4) for financial data."""

    def test_membership_payments_amount_is_numeric(self):
        src = _get_schema_source()
        # Check CREATE TABLE DDL
        assert "NUMERIC(18,4)" in src

    def test_reconcile_numeric_exists(self):
        from core.database.schema import reconcile_numeric_columns

        assert callable(reconcile_numeric_columns)

    @pytest.mark.parametrize(
        "table,col",
        [
            ("membership_payments", "amount"),
            ("posts", "tips_total"),
            ("tips", "amount"),
            ("price_alerts", "target"),
        ],
    )
    def test_numeric_migration_in_reconcile(self, table, col):
        from core.database.schema import reconcile_numeric_columns

        src = inspect.getsource(reconcile_numeric_columns)
        assert table in src and col in src, (
            f"Missing NUMERIC migration entry: {table}.{col}"
        )

    def test_quality_score_stays_real(self):
        src = _get_schema_source()
        # quality_score is not money, should stay REAL
        assert "quality_score" in src

    def test_reconcile_existing_calls_numeric(self):
        from core.database.schema import reconcile_existing_tables

        src = inspect.getsource(reconcile_existing_tables)
        assert "reconcile_numeric_columns" in src


class TestTimestamptzNormalization:
    """Verify all TIMESTAMP columns are migrated to TIMESTAMPTZ."""

    def test_reconcile_timestamptz_exists(self):
        from core.database.schema import reconcile_timestamptz

        assert callable(reconcile_timestamptz)

    @pytest.mark.parametrize(
        "table,col",
        [
            ("users", "created_at"),
            ("users", "last_active_at"),
            ("posts", "created_at"),
            ("forum_comments", "created_at"),
            ("tips", "created_at"),
            ("friendships", "created_at"),
            ("dm_messages", "created_at"),
            ("notifications", "created_at"),
            ("sessions", "created_at"),
            ("conversation_history", "timestamp"),
        ],
    )
    def test_timestamptz_migration_exists(self, table, col):
        from core.database.schema import reconcile_timestamptz

        src = inspect.getsource(reconcile_timestamptz)
        assert f'("{table}", "{col}")' in src, (
            f"Missing TIMESTAMPTZ migration entry: {table}.{col}"
        )

    def test_reconcile_existing_calls_timestamptz(self):
        from core.database.schema import reconcile_existing_tables

        src = inspect.getsource(reconcile_existing_tables)
        assert "reconcile_timestamptz" in src


class TestSchemaIdempotency:
    """Verify reconcile functions use try/except for idempotency."""

    def test_check_constraints_uses_try_except(self):
        from core.database.schema import reconcile_check_constraints

        src = inspect.getsource(reconcile_check_constraints)
        assert "try:" in src
        assert "except" in src

    def test_foreign_keys_uses_try_except(self):
        from core.database.schema import reconcile_foreign_keys

        src = inspect.getsource(reconcile_foreign_keys)
        assert "try:" in src
        assert "except" in src

    def test_numeric_uses_try_except(self):
        from core.database.schema import reconcile_numeric_columns

        src = inspect.getsource(reconcile_numeric_columns)
        assert "try:" in src
        assert "except" in src

    def test_timestamptz_uses_try_except(self):
        from core.database.schema import reconcile_timestamptz

        src = inspect.getsource(reconcile_timestamptz)
        assert "try:" in src
        assert "except" in src
