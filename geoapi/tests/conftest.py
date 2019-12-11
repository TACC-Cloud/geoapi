import pytest
import os
import json
import tempfile
import shutil
from unittest.mock import patch

import laspy

from sqlalchemy import create_engine
from geoapi.settings import settings
from geoapi.db import Base, db_session
from geoapi.models.users import User
from geoapi.models.project import Project
from geoapi.models.feature import Feature
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.features import FeaturesService
from geoapi.app import app
from geoapi.utils.assets import get_project_asset_dir


user1JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoidGVzdDEiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvYXBwcyIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdmVyc2lvbiI6IjIuMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMva2V5dHlwZSI6IlBST0RVQ1RJT04iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3VzZXJ0eXBlIjoiQVBQTElDQVRJT05fVVNFUiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlciI6InRlc3QxIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyVGVuYW50SWQiOiItOTk5OSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW1haWxhZGRyZXNzIjoidGVzdHVzZXIzQHRlc3QuY29tIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9mdWxsbmFtZSI6IkRldiBVc2VyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9naXZlbm5hbWUiOiJEZXYiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2xhc3RuYW1lIjoiVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcHJpbWFyeUNoYWxsZW5nZVF1ZXN0aW9uIjoiTi9BIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9yb2xlIjoiSW50ZXJuYWwvZXZlcnlvbmUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3RpdGxlIjoiTi9BIn0.La3pXNXcBlPIAw07U1AjJZscEWa1u4LTqRKGDVF5oeUCJzzbwUUAJo8NKH6GZR47Mks8BFBCTJGeMBLil90AkJyJpLBcKTGeAXDkcHQbPQYmGa3TYznOl6Nw1oHF6L_MX_7FFz2JDbi4OZUCRBV-f-NpNzZLdwcU1h1nalPZ0zhx5gLn2BrEhcrfw6iV6NG3VVYdXE8bPQ0cybL9RdwEi3VAIxjyxTHzYdMFAEFlHS0qav_ZojKO6r8HQg7qztjxGOjngzBIWZ_ROu8W9Msq0hsjZyX5uVqb0Ef4IoCyNkA8mw67HaeQxWZblRe6s9Z3hOv0GbFsiFgQ5xhMrg_o_Q"
user2JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoidGVzdDIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvYXBwcyIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdmVyc2lvbiI6IjIuMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMva2V5dHlwZSI6IlBST0RVQ1RJT04iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3VzZXJ0eXBlIjoiQVBQTElDQVRJT05fVVNFUiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlciI6InRlc3QyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyVGVuYW50SWQiOiItOTk5OSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW1haWxhZGRyZXNzIjoidGVzdHVzZXIzQHRlc3QuY29tIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9mdWxsbmFtZSI6IkRldiBVc2VyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9naXZlbm5hbWUiOiJEZXYiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2xhc3RuYW1lIjoiVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcHJpbWFyeUNoYWxsZW5nZVF1ZXN0aW9uIjoiTi9BIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9yb2xlIjoiSW50ZXJuYWwvZXZlcnlvbmUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3RpdGxlIjoiTi9BIn0.V6X0E_QDpUaidqjpML7CuEoiykFLXRbS0_2ulFE3CCqgTcAEuuzqOHbDKGW4XAgKpZCtj9wq5cHkIf7vpobi7Sf4HdSNIBOiIZuDWdtaSEkVG5aj7FPuGlI6dmsCq9qXd2RMHuLUGWOADmqdRoYIin_EbID1I12Mk6RqFRBz9T7wG3Pr1jn49xTvGQX2BR36qtCEQpV4FBqNsHpZi6y9oHXA-e6vPs2uQrbjtEIY9_DBE9aCt3DbYbXRFmGP8Mvn4Bm84TXytKbLoxCmncGUMP2CBYg2oRGUdHSX_nivC_1zqBPyAcW3BAIcnZ1j-ppFHAPVWiQKebZ6mOiHu2_bWA"


@pytest.fixture(scope="session")
def test_client():
    # Disable propagating of exceptions (which is enabled by default in testing/debug)
    app.config['PROPAGATE_EXCEPTIONS'] = False
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
    yield proj

    shutil.rmtree(get_project_asset_dir(1), ignore_errors=True)


@pytest.fixture(scope="function")
def point_cloud_fixture(dbsession):
    u1 = dbsession.query(User).get(1)
    data = {"description": "description"}
    point_cloud = PointCloudService.create(projectId=1, data=data, user=u1)
    yield point_cloud


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
        yield feat


@pytest.fixture(scope="function")
def image_feature_fixture(image_file_fixture):
    yield FeaturesService.fromImage(1, image_file_fixture, metadata={})


@pytest.fixture(scope="function")
def convert_to_potree_mock():
    with patch('geoapi.services.point_cloud.convert_to_potree') as mock_convert_to_potree:
        class FakeAsyncResult:
            id = "b53fdb0a-de1a-11e9-b641-0242c0a80004"
        mock_convert_to_potree.apply_async.return_value = FakeAsyncResult()
        yield mock_convert_to_potree
