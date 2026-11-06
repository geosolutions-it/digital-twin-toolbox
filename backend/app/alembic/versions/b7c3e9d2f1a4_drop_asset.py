"""drop asset table and pipeline.asset_id

Revision ID: b7c3e9d2f1a4
Revises: a1b2c3d4e5f6
Create Date: 2026-11-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b7c3e9d2f1a4'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('pipeline', 'asset_id')
    op.drop_table('asset')


def downgrade():
    op.create_table('asset',
    sa.Column('filename', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('content_size', sa.Integer(), nullable=True),
    sa.Column('asset_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('extension', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('geometry_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('upload_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('upload_status', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('upload_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('pipeline', sa.Column('asset_id', sa.Uuid(), nullable=True))
