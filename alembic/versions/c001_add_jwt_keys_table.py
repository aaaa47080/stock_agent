"""add_jwt_keys_table

Revision ID: c001_add_jwt_keys_table
Revises: 92a35ecee1cf
Create Date: 2026-03-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c001_add_jwt_keys_table"
down_revision: Union[str, Sequence[str], None] = "b003_stamp_existing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create jwt_keys table for DB-backed JWT key rotation."""
    op.create_table(
        "jwt_keys",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("deprecated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'deprecated', 'expired')",
            name="ck_jwt_key_status",
        ),
    )
    op.create_index("idx_jwt_keys_status", "jwt_keys", ["status"])
    op.create_index("idx_jwt_keys_is_primary", "jwt_keys", ["is_primary"])


def downgrade() -> None:
    """Drop jwt_keys table."""
    op.drop_index("idx_jwt_keys_is_primary", table_name="jwt_keys")
    op.drop_index("idx_jwt_keys_status", table_name="jwt_keys")
    op.drop_table("jwt_keys")
