"""replace to_ellipsoidal_height with height_reference in pipeline configs

Revision ID: 51a3b58bf878
Revises: e8b4d6f1a2c7
Create Date: 2026-11-13 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "51a3b58bf878"
down_revision = "e8b4d6f1a2c7"
branch_labels = None
depends_on = None

# table -> SQL expression of its pipeline type
TABLES = {"pipeline": "source->>'pipeline'", "pipeline_batch": "pipeline"}


def upgrade():
    for table in TABLES:
        op.execute(
            f"""
            UPDATE {table}
            SET data = (data - 'to_ellipsoidal_height')
                || CASE WHEN lower(data->>'to_ellipsoidal_height') = 'true'
                   THEN '{{"height_reference": "ellipsoidal"}}'::jsonb
                   ELSE '{{}}'::jsonb END
            WHERE jsonb_typeof(data) = 'object' AND data ? 'to_ellipsoidal_height'
            """
        )
        op.execute(
            f"""
            UPDATE {table}
            SET data = (data - 'source_vertical_epsg')
                || CASE WHEN jsonb_typeof(data->'source_vertical_epsg') = 'number'
                        AND NOT data ? 'vertical_epsg'
                   THEN jsonb_build_object('vertical_epsg', data->'source_vertical_epsg')
                   ELSE '{{}}'::jsonb END
            WHERE jsonb_typeof(data) = 'object' AND data ? 'source_vertical_epsg'
            """
        )


def downgrade():
    for table, pipeline_type in TABLES.items():
        # orthometric output has no equivalent before this revision
        op.execute(
            f"""
            UPDATE {table}
            SET data = (data - 'height_reference')
                || CASE WHEN data->>'height_reference' = 'ellipsoidal'
                   THEN '{{"to_ellipsoidal_height": true}}'::jsonb
                   ELSE '{{}}'::jsonb END
            WHERE jsonb_typeof(data) = 'object' AND data ? 'height_reference'
            """
        )
        op.execute(
            f"""
            UPDATE {table}
            SET data = (data - 'vertical_epsg')
                || jsonb_build_object('source_vertical_epsg', data->'vertical_epsg')
            WHERE {pipeline_type} = 'Terrain'
                AND jsonb_typeof(data) = 'object'
                AND jsonb_typeof(data->'vertical_epsg') = 'number'
            """
        )
