"""add_user_api_keys_table

Revision ID: 92a35ecee1cf
Revises: 4107b7e75608
Create Date: 2026-03-10 09:48:15.735458

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92a35ecee1cf'
down_revision: Union[str, Sequence[str], None] = '4107b7e75608'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add user_api_keys table."""
    op.create_table(
        'user_api_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('encrypted_key', sa.Text(), nullable=False),
        sa.Column('model_selection', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_used_at', sa.TIMESTAMP(), nullable=True),
        sa.UniqueConstraint('user_id', 'provider'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_user_api_keys_user', 'user_api_keys', ['user_id'])


def downgrade() -> None:
    """Downgrade schema: remove user_api_keys table."""
    op.drop_index('idx_user_api_keys_user', table_name='user_api_keys')
    op.drop_table('user_api_keys')
