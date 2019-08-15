import pytest
import os
import json
import tempfile
from unittest.mock import patch

import laspy

from sqlalchemy import create_engine
from geoapi.settings import settings
from geoapi.db import Base, db_session
from geoapi.models.users import User
from geoapi.models.project import Project
from geoapi.models.feature import Feature
from geoapi.app import app


user1JWT="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoidGVzdDEiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvYXBwcyIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdmVyc2lvbiI6IjIuMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMva2V5dHlwZSI6IlBST0RVQ1RJT04iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3VzZXJ0eXBlIjoiQVBQTElDQVRJT05fVVNFUiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlciI6IllPVVJfVVNFUk5BTUUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2VuZHVzZXJUZW5hbnRJZCI6IjEwIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbWFpbGFkZHJlc3MiOiJ0ZXN0dXNlcjNAdGVzdC5jb20iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2Z1bGxuYW1lIjoiVGVzdCBVc2VyMSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZ2l2ZW5uYW1lIjoiRGV2IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9sYXN0bmFtZSI6IlVzZXIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3ByaW1hcnlDaGFsbGVuZ2VRdWVzdGlvbiI6Ik4vQSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcm9sZSI6IkludGVybmFsL2V2ZXJ5b25lIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy90aXRsZSI6Ik4vQSJ9.USdVBvpmh7uEQBLSQAJcxniIdUU2coqFr4rPxCYWI8w"
user2JWT="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoidGVzdDIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvYXBwcyIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdmVyc2lvbiI6IjIuMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMva2V5dHlwZSI6IlBST0RVQ1RJT04iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3VzZXJ0eXBlIjoiQVBQTElDQVRJT05fVVNFUiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlciI6IllPVVJfVVNFUk5BTUUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2VuZHVzZXJUZW5hbnRJZCI6IjEwIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbWFpbGFkZHJlc3MiOiJ0ZXN0dXNlcjNAdGVzdC5jb20iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2Z1bGxuYW1lIjoiVGVzdCBVc2VyMSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZ2l2ZW5uYW1lIjoiRGV2IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9sYXN0bmFtZSI6IlVzZXIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3ByaW1hcnlDaGFsbGVuZ2VRdWVzdGlvbiI6Ik4vQSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcm9sZSI6IkludGVybmFsL2V2ZXJ5b25lIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy90aXRsZSI6Ik4vQSJ9.JfNlv8e_mUkdk5sm0_2ieVmaijttmLfyHSLHpDz8Ak8"


@pytest.fixture(scope="session")
def test_client():
    client = app.test_client()
    yield client


@pytest.fixture(scope='session')
def engine():
    return create_engine('postgresql://{}:{}@{}/{}'.format(
        settings.DB_USERNAME,
        settings.DB_PASSWD,
        settings.DB_HOST,
        settings.DB_NAME)
    )


@pytest.fixture(autouse=True)
def setup(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.yield_fixture(scope="function")
def dbsession(engine):
    """Returns an sqlalchemy session, and after the test tears down everything properly."""
    connection = engine.connect()
    txn = connection.begin()
    db_session.begin_nested()
    yield db_session
    db_session.remove()
    txn.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def userdata(dbsession):
    u1 = User(username="test1", jwt=user1JWT, tenant_id="test")
    u2 = User(username="test2", jwt=user2JWT, tenant_id="test")
    dbsession.add_all([u1, u2])
    dbsession.commit()


@pytest.fixture(scope="function")
def projects_fixture(dbsession):
    proj = Project(name="test", description="description")
    u1 = dbsession.query(User).get(1)
    proj.users.append(u1)
    proj.tenant_id = u1.tenant_id
    dbsession.add(proj)
    dbsession.commit()


@pytest.fixture(scope="function")
def gpx_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/run.gpx'), 'rb') as f:
        yield f


@pytest.fixture(scope="function")
def image_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/image.jpg'), 'rb') as f:
        yield f

@pytest.fixture(scope="function")
def video_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/video.mov'), 'rb') as f:
        yield f

@pytest.fixture(scope="function")
def geojson_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/geojson.json'), 'rb') as f:
        yield f


@pytest.fixture()
def lidar_las1pt2_file_path_fixture():
    home = os.path.dirname(__file__)
    return os.path.join(home, 'fixtures/lidar_subset_las1pt2.laz')


@pytest.fixture()
def lidar_las1pt4_file_path_fixture():
    home = os.path.dirname(__file__)
    return os.path.join(home, 'fixtures/lidar_subset_las1pt4.laz')


@pytest.fixture(scope="function")
def lidar_las1pt2_file_fixture(lidar_las1pt2_file_path_fixture):
    with open(lidar_las1pt2_file_path_fixture, 'rb') as f:
        yield f


@pytest.fixture(scope="function")
def empty_las_file_fixture(lidar_las1pt2_file_path_fixture):
    with tempfile.TemporaryDirectory() as temp_dir:
        empty_las_file_path = os.path.join(temp_dir, "empty.las")

        header = laspy.header.Header()
        outfile = laspy.file.File(empty_las_file_path, mode="w", header=header)
        outfile.close()

        with open(empty_las_file_path, 'rb') as f:
            yield f


@pytest.fixture(scope="function")
def feature_properties_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/properties.json'), 'rb') as f:
        yield f


@pytest.fixture(scope="function")
def feature_fixture(dbsession):
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/properties.json'), 'rb') as f:
        feat = Feature.fromGeoJSON(json.loads(f.read()))
        feat.project_id = 1
        dbsession.add(feat)
        dbsession.commit()


@pytest.fixture(scope="function")
def convert_to_potree_mock():
    with patch('geoapi.services.lidar.convert_to_potree') as mock_convert_to_potree:
        yield mock_convert_to_potree
