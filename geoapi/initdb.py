import random
from geoapi.db import Base, engine, db_session
from geoapi.models import Project, Feature, FeatureAsset, User, ProjectUser
from shapely.geometry import Point
from geoalchemy2.shape import from_shape


def initDB():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def addRandomMarkers():
    proj = Project(name="test", description="test")
    user = User(username="test")
    proj.users.append(user)
    db_session.add(user)
    for i in range(0, 10000):
        p = Point(random.uniform(-90, 90), random.uniform(-180, 180))
        feat = Feature(
            the_geom=from_shape(p, srid=4326),
        )
        feat.project = proj
        db_session.add(feat)
    db_session.commit()

if __name__ == "__main__":
    initDB()
    # addRandomMarkers()