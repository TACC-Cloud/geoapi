"""empty message

Revision ID: 8ac44fbe447a
Revises: 3f9a78c126da
Create Date: 2021-04-02 21:21:24.298681

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8ac44fbe447a'
down_revision = '3f9a78c126da'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('progress_notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('tenant_id', sa.String(), nullable=True),
    sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('progress', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=256), nullable=True),
    sa.Column('message', sa.String(length=512), nullable=True),
    sa.Column('logs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('viewed', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_progress_notifications_username'), 'progress_notifications', ['username'], unique=False)
    op.create_table('streetview',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('path', sa.String(), nullable=True),
    sa.Column('system_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_streetview_path'), 'streetview', ['path'], unique=False)
    op.create_index(op.f('ix_streetview_system_id'), 'streetview', ['system_id'], unique=False)
    op.create_index(op.f('ix_streetview_user_id'), 'streetview', ['user_id'], unique=False)
    op.create_table('streetview_sequence',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('streetview_id', sa.Integer(), nullable=True),
    sa.Column('service', sa.String(), nullable=True),
    sa.Column('start_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('end_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('bbox', sa.String(), nullable=True),
    sa.Column('sequence_key', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['streetview_id'], ['streetview.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_streetview_sequence_bbox'), 'streetview_sequence', ['bbox'], unique=False)
    op.create_index(op.f('ix_streetview_sequence_sequence_key'), 'streetview_sequence', ['sequence_key'], unique=False)
    op.create_index(op.f('ix_streetview_sequence_service'), 'streetview_sequence', ['service'], unique=False)
    op.create_index(op.f('ix_streetview_sequence_streetview_id'), 'streetview_sequence', ['streetview_id'], unique=False)
    op.add_column('users', sa.Column('google_jwt', sa.String(), nullable=True))
    op.add_column('users', sa.Column('mapillary_jwt', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'mapillary_jwt')
    op.drop_column('users', 'google_jwt')
    op.drop_index(op.f('ix_streetview_sequence_streetview_id'), table_name='streetview_sequence')
    op.drop_index(op.f('ix_streetview_sequence_service'), table_name='streetview_sequence')
    op.drop_index(op.f('ix_streetview_sequence_sequence_key'), table_name='streetview_sequence')
    op.drop_index(op.f('ix_streetview_sequence_bbox'), table_name='streetview_sequence')
    op.drop_table('streetview_sequence')
    op.drop_index(op.f('ix_streetview_user_id'), table_name='streetview')
    op.drop_index(op.f('ix_streetview_system_id'), table_name='streetview')
    op.drop_index(op.f('ix_streetview_path'), table_name='streetview')
    op.drop_table('streetview')
    op.drop_index(op.f('ix_progress_notifications_username'), table_name='progress_notifications')
    op.drop_table('progress_notifications')
    # ### end Alembic commands ###