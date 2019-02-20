from geoapi.db import Base, engine
from geoapi.models import Feature, FeatureAsset
from geoapi.models import User
from geoapi.models import Project

def initDB():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    initDB()