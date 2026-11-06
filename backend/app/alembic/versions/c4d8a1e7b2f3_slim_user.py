"""slim user to id only

Revision ID: c4d8a1e7b2f3
Revises: b7c3e9d2f1a4
Create Date: 2026-11-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'c4d8a1e7b2f3'
down_revision = 'b7c3e9d2f1a4'
branch_labels = None
depends_on = None

_COLUMNS = ('email', 'is_active', 'is_superuser', 'full_name', 'hashed_password')


def upgrade():
    op.drop_index(op.f('ix_user_email'), table_name='user')
    for name in _COLUMNS:
        op.drop_column('user', name)


def downgrade():
    op.add_column('user', sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column('user', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('user', sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('user', sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column('user', sa.Column('hashed_password', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''))
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
