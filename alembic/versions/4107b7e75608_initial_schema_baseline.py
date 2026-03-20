"""initial_schema_baseline

Revision ID: 4107b7e75608
Revises: 
Create Date: 2026-03-10 09:39:26.008144

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '4107b7e75608'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
