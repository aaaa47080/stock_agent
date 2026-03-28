"""drop_jwt_keys_table

Revision ID: c002_drop_jwt_keys_table
Revises: c001_add_jwt_keys_table
Create Date: 2026-03-29
"""

from alembic import op


revision = "c002_drop_jwt_keys_table"
down_revision = "c001_add_jwt_keys_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_jwt_keys_is_primary", table_name="jwt_keys")
    op.drop_index("idx_jwt_keys_status", table_name="jwt_keys")
    op.drop_table("jwt_keys")


def downgrade() -> None:
    pass
