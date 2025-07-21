from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import create_engine, Engine
from litestar import Litestar
from litestar.plugins.sqlalchemy import SyncSessionConfig, SQLAlchemySyncConfig, base
from typing import cast
from contextlib import asynccontextmanager, contextmanager
from collections.abc import AsyncGenerator
from geoapi.settings import settings
from geoapi.log import logger


def get_db_connection_string(conf):
    return f"postgresql://{conf.DB_USERNAME}:{conf.DB_PASSWD}@{conf.DB_HOST}/{conf.DB_NAME}"


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


def create_engine_for_context(context=None):
    return create_engine(
        get_db_connection_string(settings),
        echo=False,  # default value
        pool_pre_ping=True,
        pool_reset_on_return=True,
    )


engine = create_engine_for_context()


# class Base(DeclarativeBase):
#     pass
Base = base.DefaultBase


@contextmanager
def create_task_session():
    """Create session

    Session is used by celery tasks: it ensures they are removed and handles rollback in case of exceptions
    """
    Session = sessionmaker(
        autocommit=False, autoflush=False, bind=create_engine_for_context()
    )
    session = Session()
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
sqlalchemy_config = SQLAlchemySyncConfig(
    connection_string=get_db_connection_string(settings),
    session_config=db_session_config,
)
