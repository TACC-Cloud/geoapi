"""
Revises: 4eeeeea72dbc
Create Date: 2024-09-04 19:13:52.297379
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from geoapi.log import logger

# revision identifiers, used by Alembic.
revision = '6558809eeaed'
down_revision = '4eeeeea72dbc'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns
    op.add_column('projects', sa.Column('watch_content', sa.Boolean(), nullable=True))
    op.add_column('projects', sa.Column('watch_users', sa.Boolean(), nullable=True))

    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Query all projects and their related observable data projects in order
        # to set the watch_content and watch_users
        projects_query = sa.text("""
            SELECT p.id, odp.id as odp_id, odp.watch_content
            FROM projects p
            LEFT JOIN observable_data_projects odp ON p.id = odp.project_id
        """)
        results = session.execute(projects_query)

        # Update projects based on the query results
        for project_id, odp_id, odp_watch_content in results:
            update_query = sa.text("""
                UPDATE projects
                SET watch_content = :watch_content, watch_users = :watch_users
                WHERE id = :project_id
            """)
            session.execute(update_query, {
                'watch_content': odp_watch_content if odp_id is not None else False,
                'watch_users': odp_id is not None,
                'project_id': project_id
            })
        session.commit()
        logger.info(f"Data migration of project/observable completed successfully")

    except Exception as e:
        session.rollback()
        logger.exception(f"An error occurred during project/observable data migration: {str(e)}")
        raise
    finally:
        session.close()

    # Drop the unique constraint
    op.drop_constraint('observable_data_projects_system_id_path_key', 'observable_data_projects')


def downgrade():
    op.drop_column('projects', 'watch_users')
    op.drop_column('projects', 'watch_content')
    op.create_unique_constraint('observable_data_projects_system_id_path_key', 'observable_data_projects', ['system_id', 'path'])
