"""empty message

Revision ID: 751a1f2e8b5a
Revises: 9d043dc43f64
Create Date: 2021-04-30 21:09:16.630406

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "751a1f2e8b5a"
down_revision = "9d043dc43f64"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("projects", sa.Column("system_file", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("system_id", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("system_name", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("system_path", sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("projects", "system_path")
    op.drop_column("projects", "system_name")
    op.drop_column("projects", "system_id")
    op.drop_column("projects", "system_file")
    # ### end Alembic commands ###
