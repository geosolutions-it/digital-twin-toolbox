"""add pipeline_batch

Revision ID: e8b4d6f1a2c7
Revises: d5e9f2a3b1c6
Create Date: 2026-11-13 00:00:00.000000

"""

import posixpath
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e8b4d6f1a2c7"
down_revision = "d5e9f2a3b1c6"
branch_labels = None
depends_on = None


def _batch_rows(members):
    """One pipeline_batch row per batch_id, from its members (ordered by batch_id, title)."""
    by_batch = {}
    for m in members:
        by_batch.setdefault(m.batch_id, []).append(m)
    now = datetime.now(timezone.utc)
    rows = []
    for batch_id, group in by_batch.items():
        # the member /overview used to stand for the batch: smallest title
        first = group[0]
        source = first.source or {}
        title = first.title.split(" / ")[0] if " / " in (first.title or "") else None
        folders = [
            posixpath.dirname((m.source or {}).get("key") or "") for m in group
        ]
        common = posixpath.commonpath(folders) if all(folders) else ""
        rows.append(
            {
                "id": uuid.UUID(str(batch_id)),
                "title": title,
                "prefix": f"{common}/" if common else "",
                "pipeline": source.get("pipeline") or "PointCloud",
                "data": first.data,
                "output_prefix": source.get("batch_output_prefix"),
                "owner_id": first.owner_id,
                "created_at": now,
            }
        )
    return rows


def upgrade():
    batch = op.create_table(
        "pipeline_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("prefix", sa.String(), nullable=False),
        sa.Column("pipeline", sa.String(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_prefix", sa.String(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    pipeline = sa.table(
        "pipeline",
        sa.column("batch_id", sa.Uuid()),
        sa.column("title", sa.String()),
        sa.column("source", postgresql.JSONB()),
        sa.column("data", postgresql.JSONB()),
        sa.column("owner_id", sa.Uuid()),
    )
    members = (
        op.get_bind()
        .execute(
            sa.select(pipeline)
            .where(pipeline.c.batch_id.is_not(None))
            .order_by(pipeline.c.batch_id, pipeline.c.title)
        )
        .all()
    )
    rows = _batch_rows(members)
    if rows:
        op.bulk_insert(batch, rows)

    op.create_foreign_key(
        "pipeline_batch_id_fkey",
        "pipeline",
        "pipeline_batch",
        ["batch_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("pipeline_batch_id_fkey", "pipeline", type_="foreignkey")
    op.drop_table("pipeline_batch")
