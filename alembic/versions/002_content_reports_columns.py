"""content_reports_columns

Add points_assigned, action_taken, and processed_by columns to content_reports.

Revision ID: b002_content_reports
Revises: b001_baseline
Create Date: 2026-03-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b002_content_reports"
down_revision: Union[str, Sequence[str], None] = "b001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "content_reports",
        sa.Column("points_assigned", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "content_reports",
        sa.Column("action_taken", sa.String(50), nullable=True),
    )
    op.add_column(
        "content_reports",
        sa.Column("processed_by", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_reports", "processed_by")
    op.drop_column("content_reports", "action_taken")
    op.drop_column("content_reports", "points_assigned")
