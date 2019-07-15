from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from geoapi.settings import settings

CONNECTION_STRING = 'postgresql://{}:{}@{}/{}'.format(
    settings.DB_USERNAME,
    settings.DB_PASSWD,
    settings.DB_HOST,
    settings.DB_NAME
)
engine = create_engine(CONNECTION_STRING, echo=False)

db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

Base = declarative_base()
