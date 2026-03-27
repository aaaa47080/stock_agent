from core.orm.models import User


def test_user_model_matches_current_users_table_columns():
    columns = set(User.__table__.columns.keys())

    assert "deleted_at" not in columns
    assert {
        "user_id",
        "username",
        "auth_method",
        "pi_uid",
        "pi_username",
        "last_active_at",
        "membership_tier",
        "membership_expires_at",
        "role",
        "is_active",
        "created_at",
    }.issubset(columns)
