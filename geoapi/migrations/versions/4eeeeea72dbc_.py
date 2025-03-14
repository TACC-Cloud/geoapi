"""empty message

Revision ID: 4eeeeea72dbc
Revises: dc0c2f6ba473
Create Date: 2024-07-01 02:08:40.171299

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4eeeeea72dbc"
down_revision = "dc0c2f6ba473"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "auth",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.String(length=2048), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token", sa.String(length=2048), nullable=True),
        sa.Column(
            "refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.drop_column("users", "jwt")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "users", sa.Column("jwt", sa.VARCHAR(), autoincrement=False, nullable=True)
    )
    op.drop_table("auth")
    # ### end Alembic commands ###
