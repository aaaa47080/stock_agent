"""Tests for DB schema cleanup: dead tables, dead columns, and bug fixes."""
import inspect


class TestDeadTablesRemoved:
    """Verify unused tables are removed from schema DDL."""

    def test_login_attempts_not_in_schema(self):
        from core.database import schema
        src = inspect.getsource(schema)
        assert "CREATE TABLE IF NOT EXISTS login_attempts" not in src

    def test_tool_execution_stats_not_in_schema(self):
        from core.database import schema
        src = inspect.getsource(schema)
        assert "CREATE TABLE IF NOT EXISTS tool_execution_stats" not in src

    def test_login_attempts_index_not_in_schema(self):
        from core.database import schema
        src = inspect.getsource(schema)
        assert "idx_login_attempts" not in src

    def test_tool_execution_stats_index_not_in_schema(self):
        from core.database import schema
        src = inspect.getsource(schema)
        assert "idx_tes_" not in src

    def test_password_reset_tokens_not_in_schema(self):
        from core.database import schema
        src = inspect.getsource(schema)
        assert "CREATE TABLE IF NOT EXISTS password_reset_tokens" not in src

    def test_predictions_not_in_schema(self):
        from core.database import schema
        src = inspect.getsource(schema)
        assert "CREATE TABLE IF NOT EXISTS predictions" not in src

    def test_reconcile_drops_dead_tables(self):
        from core.database.schema import reconcile_drop_dead_tables
        src = inspect.getsource(reconcile_drop_dead_tables)
        assert "DROP TABLE" in src
        assert "login_attempts" in src
        assert "tool_execution_stats" in src
        assert "password_reset_tokens" in src
        assert "predictions" in src

    def test_reconcile_existing_includes_dead_table_cleanup(self):
        from core.database.schema import reconcile_existing_tables
        src = inspect.getsource(reconcile_existing_tables)
        assert "reconcile_drop_dead_tables" in src


class TestDeadColumnsRemoved:
    """Verify unused columns are removed from schema DDL."""

    def test_users_no_password_hash(self):
        from core.database import schema
        src = inspect.getsource(schema.create_user_tables)
        assert "password_hash" not in src

    def test_users_no_email(self):
        from core.database import schema
        src = inspect.getsource(schema.create_user_tables)
        assert "email" not in src

    def test_user_memory_cache_no_long_term_memory(self):
        from core.database import schema
        src = inspect.getsource(schema.create_memory_tables)
        assert "long_term_memory" not in src

    def test_scam_reports_no_blockchain_type(self):
        from core.database import schema
        src = inspect.getsource(schema.create_scam_tracker_tables)
        assert "blockchain_type" not in src

    def test_scam_reports_no_reporter_wallet_address(self):
        from core.database import schema
        src = inspect.getsource(schema.create_scam_tracker_tables)
        lines = src.split("\n")
        create_lines = [line for line in lines if "reporter_wallet_address" in line]
        assert not create_lines, "reporter_wallet_address should not be in CREATE TABLE"

    def test_reconcile_drops_dead_columns(self):
        from core.database.schema import reconcile_drop_dead_columns
        src = inspect.getsource(reconcile_drop_dead_columns)
        assert "users" in src
        assert "password_hash" in src
        assert "email" in src
        assert "pi_wallet_address" in src
        assert "long_term_memory" in src
        assert "blockchain_type" in src
        assert "reporter_wallet_address" in src

    def test_reconcile_existing_includes_dead_column_cleanup(self):
        from core.database.schema import reconcile_existing_tables
        src = inspect.getsource(reconcile_existing_tables)
        assert "reconcile_drop_dead_columns" in src


class TestContentReportsBugFix:
    """Verify content_reports has the columns that voting.py references."""

    def test_content_reports_has_points_assigned(self):
        from core.database import schema
        src = inspect.getsource(schema.create_governance_tables)
        assert "points_assigned" in src

    def test_content_reports_has_action_taken(self):
        from core.database import schema
        src = inspect.getsource(schema.create_governance_tables)
        assert "action_taken" in src

    def test_content_reports_has_processed_by(self):
        from core.database import schema
        src = inspect.getsource(schema.create_governance_tables)
        assert "processed_by" in src

    def test_reconcile_adds_missing_content_report_columns(self):
        from core.database.schema import reconcile_content_reports
        src = inspect.getsource(reconcile_content_reports)
        assert "points_assigned" in src
        assert "action_taken" in src
        assert "processed_by" in src

    def test_voting_update_matches_schema(self):
        from core.database.governance.voting import finalize_report
        src = inspect.getsource(finalize_report)
        assert "points_assigned" in src
        assert "action_taken" in src
        assert "processed_by" in src


class TestScamTrackerUpdated:
    """Verify scam_tracker.py INSERT no longer references removed columns."""

    def test_insert_no_blockchain_type(self):
        from core.database.scam_tracker import create_scam_report
        src = inspect.getsource(create_scam_report)
        assert "blockchain_type" not in src

    def test_insert_no_reporter_wallet_address_in_sql(self):
        from core.database.scam_tracker import create_scam_report
        src = inspect.getsource(create_scam_report)
        assert "INSERT INTO scam_reports" in src
        lines = src.split("\n")
        in_insert = False
        for line in lines:
            if "INSERT INTO" in line:
                in_insert = True
            if in_insert and ")" in line and "VALUES" not in line and line.strip() == ")":
                in_insert = False
            if in_insert and "reporter_wallet_address" in line and "masked" not in line:
                raise AssertionError(f"Found reporter_wallet_address in INSERT SQL: {line}")


class TestORMModelUpdated:
    """Verify ORM models match cleaned schema."""

    def test_user_model_no_password_hash(self):
        from core.orm.models import User
        columns = {c.name for c in User.__table__.columns}
        assert "password_hash" not in columns

    def test_user_model_no_email(self):
        from core.orm.models import User
        columns = {c.name for c in User.__table__.columns}
        assert "email" not in columns

    def test_user_repo_to_dict_no_email(self):
        from core.orm.repositories import _user_to_dict
        src = inspect.getsource(_user_to_dict)
        assert '"email"' not in src


class TestDBLayerUpdated:
    """Verify raw SQL layer no longer references removed columns."""

    def test_get_user_by_id_no_email(self):
        from core.database.user import get_user_by_id
        src = inspect.getsource(get_user_by_id)
        assert "email" not in src

    def test_pi_user_insert_no_password_hash(self):
        from core.database.user import create_or_get_pi_user
        src = inspect.getsource(create_or_get_pi_user)
        assert "password_hash" not in src
        assert "pi_wallet_address" not in src
