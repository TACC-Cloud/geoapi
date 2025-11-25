from sqlalchemy_utils import database_exists, create_database, drop_database
from sqlalchemy import text, create_engine
from alembic.config import Config
from alembic import command
from geoapi.settings import settings, UnitTestingConfig
from geoapi.db import Base, get_db_connection_string


def setup_local_dev_database():
    db_url = get_db_connection_string(settings, app_name="testing")

    # Create database if it doesn't exist
    if not database_exists(db_url):
        create_database(db_url)
        print(f"Database '{settings.DB_NAME}' created.")

    # Run all migrations
    alembic_cfg = Config("alembic.ini")
    try:
        command.upgrade(alembic_cfg, "head")
        print(
            f"All migrations have been applied. Database '{settings.DB_NAME}' is now up-to-date."
        )
    except Exception as e:
        print(f"Error applying migrations to database '{settings.DB_NAME}': {str(e)}")
        raise


def setup_unit_test_database():
    db_url = get_db_connection_string(UnitTestingConfig, app_name="testing")

    # Drop the database if it exists and recreate it
    if database_exists(db_url):
        drop_database(db_url)
    create_database(db_url)
    print(f"Test database '{UnitTestingConfig.DB_NAME}' created.")

    # Create a new engine connected to the test database
    test_engine = create_engine(db_url)

    # Enable PostGIS
    with test_engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        connection.commit()
        print("PostGIS extension enabled for test database.")

    # Create all tables based on the models
    Base.metadata.create_all(test_engine)
    print("All tables created in the test database based on current models.")


if __name__ == "__main__":
    setup_local_dev_database()
    setup_unit_test_database()
