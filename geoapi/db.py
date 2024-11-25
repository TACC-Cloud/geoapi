from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from geoapi.settings import settings
from contextlib import contextmanager
from geoapi.log import logger


def get_db_connection_string(conf):
    return f"postgresql://{conf.DB_USERNAME}:{conf.DB_PASSWD}@{conf.DB_HOST}/{conf.DB_NAME}"


def create_engine_for_context(context=None):
    engine = create_engine(
        get_db_connection_string(settings),
        echo=False,  # default value
        pool_pre_ping=True,
        pool_reset_on_return=True,
    )
    return engine


engine = create_engine_for_context()

# thread-local db session (which is used by flask requests)
db_session = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

Base = declarative_base()


@contextmanager
def create_task_session():
    """Create session

    Session is used by celery tasks: it ensures they are removed and handles rollback in case of exceptions
    """
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
