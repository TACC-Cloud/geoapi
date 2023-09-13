from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool
from geoapi.settings import settings
from contextlib import contextmanager
import os
from geoapi.log import logger


CONNECTION_STRING = 'postgresql://{}:{}@{}/{}'.format(
    settings.DB_USERNAME,
    settings.DB_PASSWD,
    settings.DB_HOST,
    settings.DB_NAME
)


def create_engine_for_context(context=None):
    context = os.environ.get('APP_CONTEXT', 'flask')  # Default to 'flask' if not provided
    logger.debug(f"Creating database engine for {context} context.")
    if context == "celery":
        # celery to disable pool (i.e. NullPool) due to https://jira.tacc.utexas.edu/browse/WG-141 and
        # https://jira.tacc.utexas.edu/browse/WG-131
        engine = create_engine(CONNECTION_STRING,
                               echo=False,  # default value
                               poolclass=NullPool)
    else:
        engine = create_engine(CONNECTION_STRING,
                               echo=False,  # default value
                               pool_pre_ping=True,
                               pool_reset_on_return=True)
    return engine


engine = create_engine_for_context()

# thread-local db session (which is used by flask requests)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

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
    except:
        logger.exception("Error occurred. Performing rollback of current database transaction")
        session.rollback()
        raise
    finally:
        session.close()
