"""update_postgis_2_5_to_3_3

Revision ID: 6495ed2ce317
Revises: 968f358e102a
Create Date: 2024-12-07 03:29:34.254577

Updates PostGIS extension to match container version (3.3). This migration drops and recreates the PostGIS
extensions to resolve library version mismatch issue.

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "6495ed2ce317"
down_revision = "968f358e102a"
branch_labels = None
depends_on = None


def upgrade():
    # Drop extensions in correct order
    op.execute("DROP EXTENSION IF EXISTS postgis_topology CASCADE;")
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")

    # Create new PostGIS extensions
    op.execute("CREATE EXTENSION postgis;")
    op.execute("CREATE EXTENSION postgis_topology;")


def downgrade():
    pass  # We don't want to downgrade PostGIS version
