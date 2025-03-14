"""empty message

Revision ID: a1f677535e21
Revises: 751a1f2e8b5a
Create Date: 2021-05-24 16:42:16.631669

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1f677535e21"
down_revision = "751a1f2e8b5a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("projects", "system_name")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "projects",
        sa.Column("system_name", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    # ### end Alembic commands ###
