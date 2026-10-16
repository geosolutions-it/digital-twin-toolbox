"""add pipeline source and batch_id

Revision ID: a1b2c3d4e5f6
Revises: 0f58b1b64e6f
Create Date: 2026-10-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '0f58b1b64e6f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pipeline', sa.Column('source', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('pipeline', sa.Column('batch_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_pipeline_batch_id'), 'pipeline', ['batch_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_pipeline_batch_id'), table_name='pipeline')
    op.drop_column('pipeline', 'batch_id')
    op.drop_column('pipeline', 'source')
