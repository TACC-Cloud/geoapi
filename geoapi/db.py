from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool
from geoapi.settings import settings
import os


CONNECTION_STRING = 'postgresql://{}:{}@{}/{}'.format(
    settings.DB_USERNAME,
    settings.DB_PASSWD,
    settings.DB_HOST,
    settings.DB_NAME
)


def create_engine_for_context():
    context = os.environ.get('APP_CONTEXT', 'flask')  # Default to 'flask' if not provided
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

db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

Base = declarative_base()
