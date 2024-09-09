import os
from sqlalchemy_utils import database_exists, create_database
from geoapi.db import engine, get_db_connection_string
from alembic.config import Config
from alembic import command
from geoapi.settings import settings


def init_database():
    db_url = get_db_connection_string(settings)

    # Create database if it doesn't exist
    if not database_exists(db_url):
        create_database(db_url)
        print(f"Database '{db_url.database}' created.")

    # Run all migrations
    alembic_cfg = Config("alembic.ini")
    try:
        command.upgrade(alembic_cfg, "head")
        print("All migrations have been applied. Database is now up-to-date.")
    except Exception as e:
        print(f"Error applying migrations: {str(e)}")
        raise


if __name__ == "__main__":
    init_database()