"""add expires_at to task

Revision ID: c1e2d3f4a5b6
Revises: 35a16955e2c9
Create Date: 2026-08-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1e2d3f4a5b6'
down_revision = '35a16955e2c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_tasks_expires_at'), 'tasks', ['expires_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tasks_expires_at'), table_name='tasks')
    op.drop_column('tasks', 'expires_at')
