from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Engine
from litestar import Litestar
from litestar.plugins.sqlalchemy import (
    SyncSessionConfig,
    SQLAlchemySyncConfig,
    base,
    EngineConfig,
)
from typing import cast
from contextlib import contextmanager
from geoapi.settings import settings
from geoapi.log import logger


def get_db_connection_string(conf, app_name=None):
    connection_string = f"postgresql://{conf.DB_USERNAME}:{conf.DB_PASSWD}@{conf.DB_HOST}/{conf.DB_NAME}"
    if app_name:
        connection_string += f"?application_name={app_name}"
    return connection_string


def get_db_connection(app: Litestar) -> Engine:
    """Returns the db engine.

    If it doesn't exist, creates it and saves it in on the application state object
    """
    if not getattr(app.state, "engine", None):
        app.state.engine = create_engine(get_db_connection_string(settings))
    return cast("Engine", app.state.engine)


def close_db_connection(app: Litestar) -> None:
    """Closes the db connection stored in the application State object."""
    if getattr(app.state, "engine", None):
        cast("Engine", app.state.engine).dispose()


def create_engine_for_migrate(context=None):
    return create_engine(
        get_db_connection_string(settings),
        echo=False,  # default value
        pool_pre_ping=True,
        pool_reset_on_return=True,
    )


migrate_engine = create_engine_for_migrate()
Base = base.DefaultBase

# The one shared engine for all Celery tasks
_celery_engine = None
_celery_sessionmaker = None


def get_celery_engine():
    """Get or create the shared Celery engine.

    This ensures all Celery tasks share ONE connection pool
    instead of creating a new engine (and pool) for every task.
    """
    global _celery_engine
    if _celery_engine is None:
        logger.info("Creating shared Celery database engine")
        _celery_engine = create_engine(
            get_db_connection_string(settings, app_name="geoapi_celery"),
            echo=False,
            pool_size=10,  # 10 persistent connections
            max_overflow=20,  # Up to 30 total connections
            pool_pre_ping=True,  # Check connection health before using
            pool_recycle=3600,  # Replace connections after 1 hour
            pool_timeout=30,  # Wait 30s for available connection
        )
    return _celery_engine


def get_celery_sessionmaker():
    """Get or create the shared Celery session maker."""
    global _celery_sessionmaker
    if _celery_sessionmaker is None:
        _celery_sessionmaker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_celery_engine(),
        )
    return _celery_sessionmaker


@contextmanager
def create_task_session():
    """Create session for Celery tasks using a shared engine.

    This ensures all tasks share ONE connection pool instead of
    creating new engines (and pools) for every task.
    """
    SessionLocal = get_celery_sessionmaker()
    session = SessionLocal()
    try:
        yield session
    except:  # noqa: E722
        logger.exception(
            "Error occurred. Performing rollback of current database transaction"
        )
        session.rollback()
        raise
    finally:
        session.close()


db_session_config = SyncSessionConfig(expire_on_commit=False, autoflush=False)
engine_config = EngineConfig(
    pool_size=20,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
)
sqlalchemy_config = SQLAlchemySyncConfig(
    connection_string=get_db_connection_string(settings, app_name="geoapi_backend_litestar"),
    session_config=db_session_config,
    engine_config=engine_config,
)