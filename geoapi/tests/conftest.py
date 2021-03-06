import pytest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage
import laspy

from geoapi.db import Base, db_session, engine
from geoapi.models.users import User
from geoapi.models.project import Project
from geoapi.models.observable_data import ObservableDataProject
from geoapi.models.feature import Feature
from geoapi.models.task import Task
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.features import FeaturesService
from geoapi.app import app
from geoapi.utils.assets import get_project_asset_dir
from geoapi.utils.agave import AgaveFileListing
from geoapi.exceptions import InvalidCoordinateReferenceSystem


# TODO: make these fixtures or something
user1JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoidGVzdDEiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvYXBwcyIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdmVyc2lvbiI6IjIuMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMva2V5dHlwZSI6IlBST0RVQ1RJT04iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3VzZXJ0eXBlIjoiQVBQTElDQVRJT05fVVNFUiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlciI6InRlc3QxIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyVGVuYW50SWQiOiItOTk5OSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW1haWxhZGRyZXNzIjoidGVzdHVzZXIzQHRlc3QuY29tIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9mdWxsbmFtZSI6IkRldiBVc2VyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9naXZlbm5hbWUiOiJEZXYiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2xhc3RuYW1lIjoiVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcHJpbWFyeUNoYWxsZW5nZVF1ZXN0aW9uIjoiTi9BIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9yb2xlIjoiSW50ZXJuYWwvZXZlcnlvbmUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3RpdGxlIjoiTi9BIn0.La3pXNXcBlPIAw07U1AjJZscEWa1u4LTqRKGDVF5oeUCJzzbwUUAJo8NKH6GZR47Mks8BFBCTJGeMBLil90AkJyJpLBcKTGeAXDkcHQbPQYmGa3TYznOl6Nw1oHF6L_MX_7FFz2JDbi4OZUCRBV-f-NpNzZLdwcU1h1nalPZ0zhx5gLn2BrEhcrfw6iV6NG3VVYdXE8bPQ0cybL9RdwEi3VAIxjyxTHzYdMFAEFlHS0qav_ZojKO6r8HQg7qztjxGOjngzBIWZ_ROu8W9Msq0hsjZyX5uVqb0Ef4IoCyNkA8mw67HaeQxWZblRe6s9Z3hOv0GbFsiFgQ5xhMrg_o_Q"
user2JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoidGVzdDIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvYXBwcyIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdmVyc2lvbiI6IjIuMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMva2V5dHlwZSI6IlBST0RVQ1RJT04iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3VzZXJ0eXBlIjoiQVBQTElDQVRJT05fVVNFUiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlciI6InRlc3QyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyVGVuYW50SWQiOiItOTk5OSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW1haWxhZGRyZXNzIjoidGVzdHVzZXIzQHRlc3QuY29tIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9mdWxsbmFtZSI6IkRldiBVc2VyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9naXZlbm5hbWUiOiJEZXYiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2xhc3RuYW1lIjoiVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcHJpbWFyeUNoYWxsZW5nZVF1ZXN0aW9uIjoiTi9BIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9yb2xlIjoiSW50ZXJuYWwvZXZlcnlvbmUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3RpdGxlIjoiTi9BIn0.V6X0E_QDpUaidqjpML7CuEoiykFLXRbS0_2ulFE3CCqgTcAEuuzqOHbDKGW4XAgKpZCtj9wq5cHkIf7vpobi7Sf4HdSNIBOiIZuDWdtaSEkVG5aj7FPuGlI6dmsCq9qXd2RMHuLUGWOADmqdRoYIin_EbID1I12Mk6RqFRBz9T7wG3Pr1jn49xTvGQX2BR36qtCEQpV4FBqNsHpZi6y9oHXA-e6vPs2uQrbjtEIY9_DBE9aCt3DbYbXRFmGP8Mvn4Bm84TXytKbLoxCmncGUMP2CBYg2oRGUdHSX_nivC_1zqBPyAcW3BAIcnZ1j-ppFHAPVWiQKebZ6mOiHu2_bWA"


@pytest.fixture
def test_client():
    # Disable propagating of exceptions (which is enabled by default in testing/debug)
    # to allow for testing of api exceptions/messages
    app.config['PROPAGATE_EXCEPTIONS'] = False

    with app.app_context():
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield app.test_client()
        db_session.remove()
        Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True, scope="function")
def userdata(test_client):
    u1 = User(username="test1", jwt=user1JWT, tenant_id="test")
    u2 = User(username="test2", jwt=user2JWT, tenant_id="test")
    db_session.add_all([u1, u2])
    db_session.commit()
    yield u1


@pytest.fixture(scope="function")
def projects_fixture():
    proj = Project(name="test", description="description")
    u1 = db_session.query(User).filter(User.username == "test1").first()
    proj.users.append(u1)
    proj.tenant_id = u1.tenant_id
    db_session.add(proj)
    db_session.commit()
    yield proj

    shutil.rmtree(get_project_asset_dir(proj.id), ignore_errors=True)


@pytest.fixture(scope="function")
def public_projects_fixture(projects_fixture):
    projects_fixture.public = True
    db_session.add(projects_fixture)
    db_session.commit()
    yield projects_fixture


@pytest.fixture(scope="function")
def observable_projects_fixture():
    u1 = db_session.query(User).filter(User.username == "test1").first()
    proj = Project(name="test_observable",
                   description="description",
                   tenant_id=u1.tenant_id)
    obs = ObservableDataProject(
        system_id="testSystem",
        path="/testPath"
    )
    obs.project = proj
    proj.users.append(u1)
    db_session.add(obs)
    db_session.add(proj)
    db_session.commit()
    yield obs

    shutil.rmtree(get_project_asset_dir(proj.id), ignore_errors=True)


@pytest.fixture(scope="function")
def point_cloud_fixture():
    u1 = db_session.query(User).filter(User.username == "test1").first()
    data = {"description": "description"}
    point_cloud = PointCloudService.create(projectId=1, data=data, user=u1)
    yield point_cloud


@pytest.fixture(scope="function")
def task_fixture():
    task = Task(process_id="1234", status="SUCCESS", description="description")
    db_session.add(task)
    db_session.commit()
    yield task


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
def flipped_image_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/flipped_image.jpg'), 'rb') as f:
        yield f


@pytest.fixture(scope="function")
def corrected_image_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/corrected_image.jpg'), 'rb') as f:
        yield f


@pytest.fixture()
def hazmpperV1_file():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/hazmapperv1_with_images.json'), 'rb') as f:
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
def lidar_las_epsg7030_file_path_fixture():
    home = os.path.dirname(__file__)
    return os.path.join(home, 'fixtures/lidar_subset_epsg7030.las')


@pytest.fixture()
def lidar_las1pt4_file_path_fixture():
    home = os.path.dirname(__file__)
    return os.path.join(home, 'fixtures/lidar_subset_las1pt4.laz')


@pytest.fixture(scope="function")
def empty_las_file_path_fixture():
    with tempfile.TemporaryDirectory() as temp_dir:
        empty_las_file_path = os.path.join(temp_dir, "empty.las")

        header = laspy.header.Header()
        outfile = laspy.file.File(empty_las_file_path, mode="w", header=header)
        outfile.close()
        yield empty_las_file_path


@pytest.fixture(scope="function")
def lidar_las1pt2_file_fixture(lidar_las1pt2_file_path_fixture):
    with open(lidar_las1pt2_file_path_fixture, 'rb') as f:
        yield f


@pytest.fixture(scope="function")
def empty_las_file_fixture(empty_las_file_path_fixture):
    with open(empty_las_file_path_fixture, 'rb') as f:
        yield f


@pytest.fixture(scope="function")
def shapefile_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/shapefile.shp'), 'rb') as f:
        yield FileStorage(f)


@pytest.fixture(scope="function")
def shapefile_additional_files_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/shapefile.cpg'), 'rb') as cpg,\
            open(os.path.join(home, 'fixtures/shapefile.dbf'), 'rb') as dbf,\
            open(os.path.join(home, 'fixtures/shapefile.prj'), 'rb') as prj,\
            open(os.path.join(home, 'fixtures/shapefile.shx'), 'rb') as shx:
        yield [FileStorage(cpg), FileStorage(dbf), FileStorage(prj), FileStorage(shx)]


@pytest.fixture()
def shapefile_first_element_geometry():
    """
    geometry (in epsg 4326) of first element in shapefile_fixture
    """
    wkt = ("MULTIPOLYGON (((-68.63401022758323 -52.63637045887449, -68.63335000000001 -54.8695,"
           " -67.56244 -54.87001, -66.95992000000001 -54.89681000000002,"
           " -67.29102999999992 -55.30123999999995, -68.14862999999991 -55.61183,"
           " -68.63999081081187 -55.58001799908692, -69.2321 -55.49905999999993,"
           " -69.95808999999997 -55.19843000000003, -71.00567999999998 -55.05383,"
           " -72.26390000000004 -54.49513999999999, -73.28519999999997 -53.95751999999993,"
           " -74.66253 -52.83748999999995, -73.8381 -53.04743000000002,"
           " -72.43417999999997 -53.71539999999999, -71.10773 -54.07432999999992,"
           " -70.59177999999986 -53.61582999999996, -70.26747999999998 -52.93123000000003,"
           " -69.34564999999992 -52.51829999999995, -68.63401022758323 -52.63637045887449)),"
           " ((-69.59042375352405 -17.58001189541933, -69.10024695501949 -18.26012542081268,"
           " -68.96681840684187 -18.98168344490411, -68.44222510443092 -19.40506845467143,"
           " -68.75716712103375 -20.37265797290446, -68.21991309271128 -21.49434661223187,"
           " -67.82817989772273 -22.87291879648217, -67.1066735500636 -22.73592457447642,"
           " -66.9852339341777 -22.98634856536284, -67.32844295924417 -24.02530323659095,"
           " -68.41765296087614 -24.51855478281688, -68.38600114609736 -26.18501637136522,"
           " -68.59479977077268 -26.5069088681113, -68.29554155137043 -26.89933969493578,"
           " -69.00123491074825 -27.52121388113618, -69.65613033718317 -28.45914112723369,"
           " -70.01355038112992 -29.36792286551857, -69.91900834825194 -30.33633920666828,"
           " -70.53506893581951 -31.36501026787031, -70.07439938015359 -33.09120981214805,"
           " -69.81477698431922 -33.27388600029983, -69.81730912950152 -34.1935714657983,"
           " -70.38804948594913 -35.16968759535949, -70.36476925320164 -36.00508879978992,"
           " -71.12188066270987 -36.65812387466232, -71.11862504747549 -37.57682748794724,"
           " -70.81466427273469 -38.55299529394074, -71.41351660834906 -38.91602223079114,"
           " -71.68076127794649 -39.80816415787805, -71.91573401557763 -40.83233936947069,"
           " -71.7468037584155 -42.05138640723598, -72.14889807807856 -42.25488819760137,"
           " -71.91542395698389 -43.40856454851745, -71.46405615913051 -43.78761117937835,"
           " -71.79362260607193 -44.20717213315606, -71.32980078803622 -44.40752166115166,"
           " -71.22277889675976 -44.78424285255942, -71.65931555854536 -44.97368865334143,"
           " -71.55200944689128 -45.5607329241771, -71.91725847033024 -46.88483814879177,"
           " -72.44735531278027 -47.73853281025352, -72.33116085477201 -48.2442383766618,"
           " -72.64824744331494 -48.87861825947683, -73.41543575712009 -49.31843637471297,"
           " -73.32805091011453 -50.37878508890991, -72.97574683296469 -50.74145029073429,"
           " -72.30997351753234 -50.67700977966632, -72.32940385607407 -51.42595631287243,"
           " -71.91480383979638 -52.0090223058659, -69.49836218939609 -52.14276091263727,"
           " -68.57154537624133 -52.29944385534623, -69.46128434922667 -52.29195077266391,"
           " -69.9427795071062 -52.53793059037322, -70.8451016913546 -52.89920052852571,"
           " -71.00633216010525 -53.83325204220132, -71.429794684521 -53.85645476030037,"
           " -72.55794287788488 -53.53141000118449, -73.7027567206629 -52.83506926860723,"
           " -73.7027567206629 -52.83507007605149, -74.94676347522517 -52.262753588419,"
           " -75.26002600777851 -51.62935475037325, -74.97663245308988 -51.0433956846157,"
           " -75.47975419788355 -50.37837167745158, -75.60801510283198 -48.67377288187184,"
           " -75.18276974150216 -47.7119194476232, -74.12658098010471 -46.93925343199511,"
           " -75.64439531116545 -46.64764332457207, -74.69215369332312 -45.76397633238103,"
           " -74.35170935738425 -44.10304412208794, -73.24035600451522 -44.4549606259956,"
           " -72.71780392117979 -42.38335580827898, -73.38889990913822 -42.11753224056957,"
           " -73.70133561877488 -43.36577646257977, -74.33194312203261 -43.22495818458442,"
           " -74.01795711942719 -41.79481292090683, -73.67709937202999 -39.94221282324317,"
           " -73.21759253609065 -39.25868865331856, -73.50555945503712 -38.28288258235111,"
           " -73.58806087919109 -37.15628468195598, -73.1667170884993 -37.12378020604439,"
           " -72.55313696968174 -35.50884002049106, -71.86173214383263 -33.90909270603153,"
           " -71.4384504869299 -32.41889942803078, -71.66872066922247 -30.92064462659249,"
           " -71.37008256700773 -30.09568206148503, -71.48989437527645 -28.86144215262592,"
           " -70.90512386746161 -27.64037973400125, -70.72495398627599 -25.70592416758726,"
           " -70.40396582709502 -23.62899667734457, -70.09124589708074 -21.39331918710126,"
           " -70.16441972520605 -19.75646819425616, -70.37257239447771 -18.34797535570887,"
           " -69.85844356960587 -18.09269378018701, -69.59042375352405 -17.58001189541933)))")
    yield wkt


@pytest.fixture(scope="function")
def feature_properties_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/properties.json'), 'rb') as f:
        yield f


@pytest.fixture(scope="function")
def feature_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/properties.json'), 'rb') as f:
        feat = Feature.fromGeoJSON(json.loads(f.read()))
        feat.project_id = 1
        db_session.add(feat)
        db_session.commit()
        yield feat


@pytest.fixture(scope="function")
def image_feature_fixture(image_file_fixture):
    yield FeaturesService.fromImage(1, image_file_fixture, metadata={})


@pytest.fixture(scope="function")
def import_file_from_agave_mock():
    with patch('geoapi.tasks.external_data.import_file_from_agave') as import_file_from_agave:
        yield import_file_from_agave


@pytest.fixture(scope="function")
def import_from_agave_mock():
    with patch('geoapi.services.projects.import_from_agave') as mock_import:
        yield mock_import


@pytest.fixture(scope="function")
def convert_to_potree_mock():
    with patch('geoapi.services.point_cloud.convert_to_potree') as mock_convert_to_potree:
        class FakeAsyncResult:
            id = "b53fdb0a-de1a-11e9-b641-0242c0a80004"

        mock_convert_to_potree.apply_async.return_value = FakeAsyncResult()
        yield mock_convert_to_potree


@pytest.fixture(scope="function")
def check_point_cloud_mock():
    with patch('geoapi.services.point_cloud.check_point_cloud') as mock_check_point_cloud_mock:
        class FakeAsyncResult:
            def get(self):
                return None
        mock_check_point_cloud_mock.apply_async.return_value = FakeAsyncResult()
        yield mock_check_point_cloud_mock


@pytest.fixture(scope="function")
def check_point_cloud_mock_missing_crs():
    with patch('geoapi.services.point_cloud.check_point_cloud') as mock_check_point_cloud_mock:
        mock_result = MagicMock()
        mock_result.get.side_effect = InvalidCoordinateReferenceSystem()
        mock_check_point_cloud_mock.apply_async.return_value = mock_result
        yield mock_check_point_cloud_mock


@pytest.fixture(scope="function")
def get_point_cloud_info_mock():
    with patch('geoapi.services.point_cloud.get_point_cloud_info') as mock_get_point_cloud_info:
        mock_result = MagicMock()
        mock_result.get.return_value = [{'name': 'test.las'}]

        mock_get_point_cloud_info.apply_async.return_value = mock_result
        yield mock_get_point_cloud_info


@pytest.fixture(scope="function")
def agave_file_listings_mock():
    filesListing = [
        AgaveFileListing({
            "system": "testSystem",
            "path": "/testPath",
            "type": "dir",
            "length": 4,
            "_links": "links",
            "mimeType": "folder",
            "lastModified": "2020-08-31T12:00:00Z"
        }),
        AgaveFileListing({
            "system": "testSystem",
            "type": "file",
            "length": 4096,
            "path": "/testPath/file.json",
            "_links": "links",
            "mimeType": "application/json",
            "lastModified": "2020-08-31T12:00:00Z"
        })
    ]
    yield filesListing


@pytest.fixture(scope="function")
def agave_utils_with_geojson_file_mock(agave_file_listings_mock, geojson_file_fixture):
    with patch('geoapi.services.projects.AgaveUtils') as MockAgaveUtils:
        MockAgaveUtils().listing.return_value = agave_file_listings_mock
        MockAgaveUtils().getFile.return_value = geojson_file_fixture
        MockAgaveUtils().systemsGet.return_value = {"id": "testSystem",
                                                    "description": "System Description"}
        yield MockAgaveUtils()


@pytest.fixture(scope="function")
def get_system_users_mock(userdata):
    u1 = db_session.query(User).get(1)
    u2 = db_session.query(User).get(2)
    with patch('geoapi.services.projects.get_system_users', return_value=[u1.username, u2.username]) as get_system_users:
        yield get_system_users


@pytest.fixture(scope="function")
def tile_server_ini_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, 'fixtures/metadata.ini'), 'rb') as f:
        yield f
