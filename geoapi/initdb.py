from geoapi.db import Base, engine
from geoapi.models import Feature
from geoapi.models import User
from geoapi.models import LayerGroup
from geoapi.models import Project

def initDB():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
