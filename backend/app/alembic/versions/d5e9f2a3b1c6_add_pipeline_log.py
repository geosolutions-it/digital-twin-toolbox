"""add pipeline_log

Revision ID: d5e9f2a3b1c6
Revises: c4d8a1e7b2f3
Create Date: 2026-11-12 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd5e9f2a3b1c6'
down_revision = 'c4d8a1e7b2f3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pipeline_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('pipeline_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('stage', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipeline.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pipeline_log_pipeline_id'), 'pipeline_log', ['pipeline_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_pipeline_log_pipeline_id'), table_name='pipeline_log')
    op.drop_table('pipeline_log')
