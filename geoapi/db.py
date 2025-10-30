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


def get_db_connection_string(conf, app_name):
    connection_string = f"postgresql://{conf.DB_USERNAME}:{conf.DB_PASSWD}@{conf.DB_HOST}/{conf.DB_NAME}"
    connection_string += f"?application_name={app_name}_{conf.APP_ENV}"
    return connection_string


def close_db_connection(app: Litestar) -> None:
    """Closes the db connection stored in the application State object."""
    if getattr(app.state, "engine", None):
        cast("Engine", app.state.engine).dispose()


def create_engine_for_migrate(context=None):
    return create_engine(
        get_db_connection_string(settings, app_name="migrate"),
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
            max_overflow=45,  # Up to 55 total connections
            pool_pre_ping=True,  # Check connection health before using
            pool_recycle=3600,  # Replace connections after 1 hour
            pool_timeout=60,  # Wait up to 60s for connection
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

# Connection pool sizing for Litestar HTTP workers:
# - 8 persistent + 7 overflow = 15 connections per Litestar worker
# - 9 Litestar workers (docker-compose.yml -W 9) × 15 = 135 connections
# - 135 connections to geoapi-database.tacc.utexas.edu
#
# Note: Celery workers run separately with shared pool supporting ~52 concurrent tasks
# (46 default queue on prod + 6 heavy queue). Pool: 20 + 35 overflow = 55 connections max.
# See get_celery_engine()
#
# Total production connections: ~135 (Litestar) + 55 (Celery) = 190 of 200 max
# Across 3 environments (prod/staging/dev): prod uses ~190
litestar_engine_config = EngineConfig(
    pool_size=8,  # 8 persistent connections per Litestar worker
    max_overflow=7,  # Up to 7 additional connections per Litestar worker (8+7=15 total per worker)
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
)
litestar_sqlalchemy_config = SQLAlchemySyncConfig(
    connection_string=get_db_connection_string(
        settings, app_name="geoapi_backend_litestar"
    ),
    session_config=db_session_config,
    engine_config=litestar_engine_config,
)


@contextmanager
def managed_litestar_db_session(app_state=None, scope=None):
    db_session = litestar_sqlalchemy_config.provide_session(app_state, scope)

    try:
        yield db_session
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
