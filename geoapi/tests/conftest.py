import pytest
import os
import json
import tempfile
import shutil
import laspy
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage
from typing import TYPE_CHECKING
from collections.abc import Iterator
from litestar.testing import TestClient
from geoapi.db import Base, sqlalchemy_config
from geoapi.models.users import User
from geoapi.models.project import Project, ProjectUser
from geoapi.models.feature import Feature
from geoapi.models.task import Task
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.features import FeaturesService
from geoapi.services.users import UserService
from geoapi.app import app, session_auth_config
from geoapi.utils.assets import get_project_asset_dir
from geoapi.utils.external_apis import TapisFileListing, SystemUser
from geoapi.utils.tenants import get_tapis_api_server
from geoapi.utils.jwt_utils import create_token_expiry_hours_from_now
from geoapi.exceptions import InvalidCoordinateReferenceSystem

if TYPE_CHECKING:
    from litestar import Litestar


@pytest.fixture(scope="session")
def db_engine() -> "Iterator[sqlalchemy_config.Engine]":
    """Create the database engine for testing."""
    db_engine = sqlalchemy_config.get_engine()
    yield db_engine


@pytest.fixture(scope="function")
def create_tables(db_engine) -> "Iterator[None]":
    """Create the database tables for testing."""
    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)
    yield db_engine
    Base.metadata.drop_all(db_engine)


@pytest.fixture(scope="function")
def db_session(db_engine, create_tables) -> "Iterator[sqlalchemy_config.Session]":
    """Create a database session for testing."""
    sqlalchemy_config.engine_instance = db_engine
    with sqlalchemy_config.get_session() as session:
        yield session


@pytest.fixture(scope="function")
def test_client_user1() -> "Iterator[TestClient[Litestar]]":

    with TestClient(app=app, session_config=session_auth_config) as client:
        client.set_session_data({"username": "test1", "tenant": "test"})
        yield client


@pytest.fixture(scope="function")
def test_client_user2() -> "Iterator[TestClient[Litestar]]":

    with TestClient(app=app, session_config=session_auth_config) as client:
        client.set_session_data({"username": "test2", "tenant": "test"})
        yield client


@pytest.fixture(scope="function")
def test_client() -> "Iterator[TestClient[Litestar]]":

    with TestClient(app=app, session_config=session_auth_config) as client:
        yield client


@pytest.fixture(autouse=True, scope="function")
def userdata(create_tables, db_engine) -> "Iterator[User]":
    user1JWT = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJjY2Q2Y2UwZS0xNTY4LTRjNTItYTVlYy03MGE3YTc2M2M0YTMiLCJpc3MiOiJodHRwczovL2Rlc2lnbnNhZmUudGFwaXMuaW8vdjMvdG9rZW5zIiwic3ViIjoidGVzdDNAZGVzaWduc2FmZSIsInRhcGlzL3RlbmFudF9pZCI6InRlc3QiLCJ0YXBpcy90b2tlbl90eXBlIjoiYWNjZXNzIiwidGFwaXMvZGVsZWdhdGlvbiI6ZmFsc2UsInRhcGlzL2RlbGVnYXRpb25fc3ViIjpudWxsLCJ0YXBpcy91c2VybmFtZSI6InRlc3QxIiwidGFwaXMvYWNjb3VudF90eXBlIjoidXNlciIsImV4cCI6MTcwODExOTU1OCwidGFwaXMvY2xpZW50X2lkIjoiaGF6bWFwcGVyLnRlc3QiLCJ0YXBpcy9ncmFudF90eXBlIjoiaW1wbGljaXQifQ.ILmDPdffMv9BuSbXifiPam4OTMFnUrcrPsgywQK6RSG4PYuZZyJ5IQhcr06bqdv3xieFI623HVOK_wUi4mgrckeFf3sU5eT9Wv6cEjiBxsO1-PT8QNFzAEvBlpVFjlZ_XzimoR6G3Jg636zejkNOhlNkgVIvv7iUta0oLIJHMei_gvIqRYjisTfva8NxhpG5aUBxTgOP_UEpJyM7k0UrEhqc9LtcFgstUp9PemSMMdRfbD4TftxeAD6EKrRrofRpsi3hmpP-aWXOOZRGiqx87GvMCUzZ-5T2uLBBFF7SDcM-JEGY90awC4oAlDk5RIFdWo-oIOzQyuj1f2Wg3USPfhpF0CRqp_ISQ9c4gjFaEQn299nobCq5fKI-BVYOCYfHgh0fsrMhri7g53M_ozhmi9RPUFfRXr4xhlUfvfZVCDE78GyeQfRu_oJcezxgXVLuVyajwQbPfLZ1xJ2952vTj-uA5pAXW0SR5jkIM_0M2YfqhW0JhPyw8xw7lFDaR0C2DFDQ8hqxFnh1keqNM6fWS4jFLLqcnEYnw2-g_BLXE96AIcw18bWtafHmyJ4Zun2OEByvGlywbYtknO3NpJiBUiLXpdNdGELAO9NKvyCIeOjfstXl75SHYi1DC6YAc_ZzL3F0-ZXtz3NASQejn8ceu0awoVESU1mMPXUHu2bJYts"  # noqa: E501
    user2JWT = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJjY2Q2Y2UwZS0xNTY4LTRjNTItYTVlYy03MGE3YTc2M2M0YTMiLCJpc3MiOiJodHRwczovL2Rlc2lnbnNhZmUudGFwaXMuaW8vdjMvdG9rZW5zIiwic3ViIjoidGVzdDNAZGVzaWduc2FmZSIsInRhcGlzL3RlbmFudF9pZCI6InRlc3QiLCJ0YXBpcy90b2tlbl90eXBlIjoiYWNjZXNzIiwidGFwaXMvZGVsZWdhdGlvbiI6ZmFsc2UsInRhcGlzL2RlbGVnYXRpb25fc3ViIjpudWxsLCJ0YXBpcy91c2VybmFtZSI6InRlc3QyIiwidGFwaXMvYWNjb3VudF90eXBlIjoidXNlciIsImV4cCI6MTcwODExOTU1OCwidGFwaXMvY2xpZW50X2lkIjoiaGF6bWFwcGVyLnRlc3QiLCJ0YXBpcy9ncmFudF90eXBlIjoiaW1wbGljaXQifQ.lsa8XEIXkb_4rkzFdVpuwCIcWrwAolLN7Gx0K2V6KdcTVWLrUn_5ZONr5AoCPOeV6SR14Bs5kpZdZB5bxfyf0z7OWIRbsRJgyThSle3LS-bdA8ltflFOW-coZsDd4C_eXfj-8b0RM1JTRHCkS3daFUeJOLL6QDnhoENiY4FlT-1WTydgw_f2T4BRPatqwQPZajBfnOVs9cwlhsS0HuDJVRWV4zh78jckW3jPdZ_JybjwGy9w32cSFm2BTASdvUfuCN4CJfY1QwJP7jlZno377MJnsCypW-CJyF57LbEZ_dqgQVVFVGLWS_zd5zmhctxtDtaC80e8jkS6Ld1F1duNHSU0GUfURBg_aoi1vBzlE6h49MfLxCtX0oOhiysoQeiZpBV4F-ZkNhULw_GrKm7JNUsHvTsRUb61tkje2uVN-YefqsZYQ7apwRQ7S5oU0ccNXubCp_uk6TNSHB7cZMiElnWJalRZlOo0MD7Lx7NXlohCaK_ICh5BMSS1jKzhBxj-ug5O2R3oGIztNkHlUp3F476aWN8bRtVOobFgk4MhRBahWqAgrbpLHbk5OSyCeSQ_brB9avjoNl8e23mJTKQIO6HDc_QqsA586buXT3deb5d4QaqzGWkSwmZs6_kozDnbOItYJC-6E4qm25AX8ew4NHmLrPvtYW66FT-UCI5LiBU"  # noqa: E501
    user3JWT = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJjY2Q2Y2UwZS0xNTY4LTRjNTItYTVlYy03MGE3YTc2M2M0YTMiLCJpc3MiOiJodHRwczovL2Rlc2lnbnNhZmUudGFwaXMuaW8vdjMvdG9rZW5zIiwic3ViIjoidGVzdDNAZGVzaWduc2FmZSIsInRhcGlzL3RlbmFudF9pZCI6InRlc3QiLCJ0YXBpcy90b2tlbl90eXBlIjoiYWNjZXNzIiwidGFwaXMvZGVsZWdhdGlvbiI6ZmFsc2UsInRhcGlzL2RlbGVnYXRpb25fc3ViIjpudWxsLCJ0YXBpcy91c2VybmFtZSI6InRlc3QzIiwidGFwaXMvYWNjb3VudF90eXBlIjoidXNlciIsImV4cCI6MTcwODExOTU1OCwidGFwaXMvY2xpZW50X2lkIjoiaGF6bWFwcGVyLnRlc3QiLCJ0YXBpcy9ncmFudF90eXBlIjoiaW1wbGljaXQifQ.Ojtx5fCZGFHxl7zXdH6j2OPBdVHvp_MCGJMeg_sTNuAqT-gVf_L81h1Zqrh9gdLR4og1n-V4yQp8aYQsUJ_jBv_9OIvF4KuYa2hAN9Bn-FAL0VngJUU1wHvkLYlTpLGmTnhgTdtOi2Xj_geNNKgs3EsWacqZwE7-lUKv0YtsVvjb_Z5fZUjXzjxg4jWIx7FhHqz2bodT8WNU7eMPE2oNgwPFjkouoi5yELLmAHE_8bvudlW4sbIiO16cFGfH3xdzDi7TsfZa_Nmqg1x6BHHQ-n47yB0q87ntJ4MiS7cGio8C0x1j25eohjFkQ0ztj3F3KfQMuVb9nFc3JBjtycDbfqvIIzFIqf7eLso5oWqioPPnAi0DG7THIad2XzRPPB6Ri2jtbc8cDHlVOadwXNndud8fjdPSOQ68mFwMMj4-24ndhxf-Tp8MrvXpo91It66KescGQyFt5tFNGDZtzXdve4L6HUHdP9yaYEPmPEtvAODqUJTLAx088NuIxIcDvSRe_pHWKnkkYNPvdsJcXspw2KYTJjNRrVxjIY5mOLMsCtJQug8VZVWJ6wk7zDnpvnaD8CzFIl2ge5ECZtAuD1MtBfIR45j0shynDs8JiX2vH6-0z03zFU_OWSXXGppZBLIjrgcIJEVIFF0F64na3ZH6Zlt56ZoZngRjNGHypD3XZGA"  # noqa: E501

    user1JWT = create_token_expiry_hours_from_now(user1JWT)
    user2JWT = create_token_expiry_hours_from_now(user2JWT)
    user3JWT = create_token_expiry_hours_from_now(user3JWT)

    sqlalchemy_config.engine_instance = db_engine
    with sqlalchemy_config.get_session() as session:
        u1 = UserService.create(
            session, username="test1", access_token=user1JWT, tenant="test"
        )
        UserService.create(
            session, username="test2", access_token=user2JWT, tenant="test"
        )
        UserService.create(
            session, username="test3", access_token=user3JWT, tenant="test"
        )
        yield u1


@pytest.fixture(autouse=True, scope="function")
def tapis_url(user1):
    yield get_tapis_api_server(user1.tenant_id)


@pytest.fixture(scope="function")
def user1(userdata, db_session: "sqlalchemy_config.Session") -> "Iterator[User]":
    yield db_session.query(User).filter(User.username == "test1").first()


@pytest.fixture(scope="function")
def user2(userdata, db_session: "sqlalchemy_config.Session") -> "Iterator[User]":
    yield db_session.query(User).filter(User.username == "test2").first()


@pytest.fixture(scope="function")
def projects_fixture(db_session: "sqlalchemy_config.Session") -> "Iterator[Project]":
    """Project with 1 user and test1 is an admin"""
    project = Project(name="test", description="description")
    u1 = db_session.query(User).filter(User.username == "test1").first()
    project.users.append(u1)

    project.tenant_id = u1.tenant_id
    db_session.add(project)
    db_session.commit()

    project_user1 = (
        db_session.query(ProjectUser)
        .filter(ProjectUser.project_id == project.id)
        .first()
    )
    project_user1.admin = True
    db_session.add(project_user1)
    db_session.commit()

    yield project

    shutil.rmtree(get_project_asset_dir(project.id), ignore_errors=True)


@pytest.fixture(scope="function")
def projects_fixture2(
    user1, user2, db_session: "sqlalchemy_config.Session"
) -> "Iterator[Project]":
    """Project with 2 users and test1 is creator"""
    ""
    project = Project(name="test2", description="description2")
    project.users.append(user1)
    project.users.append(user2)
    project.tenant_id = user1.tenant_id
    db_session.add(project)
    db_session.commit()

    project_user1 = (
        db_session.query(ProjectUser)
        .filter(ProjectUser.project_id == project.id)
        .filter(ProjectUser.user_id == user1.id)
        .first()
    )
    project_user1.creator = True

    db_session.add(project_user1)
    db_session.commit()

    yield project

    shutil.rmtree(get_project_asset_dir(project.id), ignore_errors=True)


@pytest.fixture(scope="function")
def public_projects_fixture(
    projects_fixture, db_session: "sqlalchemy_config.Session"
) -> "Iterator[Project]":
    projects_fixture.public = True
    db_session.add(projects_fixture)
    db_session.commit()
    yield projects_fixture


@pytest.fixture(scope="function")
def watch_content_users_projects_fixture(
    db_session: "sqlalchemy_config.Session",
) -> "Iterator[Project]":
    u1 = db_session.query(User).filter(User.username == "test1").first()
    project = Project(
        name="test_observable",
        description="description",
        tenant_id=u1.tenant_id,
        system_id="project-1234",
        system_path="/testPath",
        system_file="system_file",  # system_file.hazmapper
        watch_content=True,
        watch_users=True,
    )
    project.users.append(u1)
    db_session.add(project)
    db_session.commit()
    project.project_users[0].creator = True
    db_session.commit()
    yield project

    shutil.rmtree(get_project_asset_dir(project.id), ignore_errors=True)


@pytest.fixture(scope="function")
def point_cloud_fixture(
    db_session: "sqlalchemy_config.Session",
) -> "Iterator[PointCloudService]":
    u1 = db_session.query(User).filter(User.username == "test1").first()
    data = {"description": "description"}
    point_cloud = PointCloudService.create(db_session, projectId=1, data=data, user=u1)
    yield point_cloud


@pytest.fixture(scope="function")
def task_fixture(db_session: "sqlalchemy_config.Session") -> "Iterator[Task]":
    task = Task(process_id="1234", status="SUCCESS", description="description")
    db_session.add(task)
    db_session.commit()
    yield task


@pytest.fixture(scope="function")
def gpx_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/run.gpx"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def image_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/image.jpg"), "rb") as f:
        f.filename = "image.jpg"
        yield f


@pytest.fixture(scope="function")
def image_file_no_location_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/image_no_location_data.jpg"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def image_small_DES_2176_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/image_small_file_DES_2176.jpg"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def video_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/video.mov"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def flipped_image_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/flipped_image.jpg"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def corrected_image_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/corrected_image.jpg"), "rb") as f:
        yield f


@pytest.fixture()
def hazmpperV1_file():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/hazmapperv1_with_images.json"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def geojson_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/geojson.json"), "rb") as f:
        yield f


@pytest.fixture()
def lidar_las1pt2_file_path_fixture():
    home = os.path.dirname(__file__)
    return os.path.join(home, "fixtures/lidar_subset_las1pt2.las")


@pytest.fixture()
def lidar_las_epsg7030_file_path_fixture():
    home = os.path.dirname(__file__)
    return os.path.join(home, "fixtures/lidar_subset_epsg7030.las")


@pytest.fixture()
def lidar_las1pt4_file_path_fixture():
    home = os.path.dirname(__file__)
    return os.path.join(home, "fixtures/lidar_subset_las1pt4.las")


@pytest.fixture()
def lidar_medium_size_compressed_las1pt2():
    home = os.path.dirname(__file__)
    return os.path.join(
        home, "fixtures/lidar_medium_subset_las1pt2_utmzone13N_compressed.laz"
    )


@pytest.fixture(scope="function")
def empty_las_file_path_fixture():
    with tempfile.TemporaryDirectory() as temp_dir:
        empty_las_file_path = os.path.join(temp_dir, "empty.las")

        header = laspy.header.LasHeader()
        outfile = laspy.LasData(header)
        outfile.write(empty_las_file_path)
        yield empty_las_file_path


@pytest.fixture(scope="function")
def lidar_las1pt2_file_fixture(lidar_las1pt2_file_path_fixture):
    with open(lidar_las1pt2_file_path_fixture, "rb") as f:
        yield f


@pytest.fixture(scope="function")
def empty_las_file_fixture(empty_las_file_path_fixture):
    with open(empty_las_file_path_fixture, "rb") as f:
        yield f


@pytest.fixture(scope="function")
def shapefile_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/shapefile.shp"), "rb") as f:
        yield FileStorage(f)


@pytest.fixture(scope="function")
def shapefile_additional_files_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/shapefile.cpg"), "rb") as cpg, open(
        os.path.join(home, "fixtures/shapefile.dbf"), "rb"
    ) as dbf, open(os.path.join(home, "fixtures/shapefile.prj"), "rb") as prj, open(
        os.path.join(home, "fixtures/shapefile.shx"), "rb"
    ) as shx:
        yield [FileStorage(cpg), FileStorage(dbf), FileStorage(prj), FileStorage(shx)]


@pytest.fixture()
def shapefile_first_element_geometry():
    """
    geometry (in epsg 4326) of first element in shapefile_fixture
    """
    wkt = (
        "MULTIPOLYGON (((-68.63401022758323 -52.63637045887449, -68.63335000000001 -54.869499999999995,"
        " -67.56244 -54.87001, -66.95992000000001 -54.896810000000016,"
        " -67.29102999999992 -55.30123999999995, -68.14862999999991 -55.61183,"
        " -68.63999081081187 -55.58001799908692, -69.2321 -55.49905999999993,"
        " -69.95808999999997 -55.19843000000003, -71.00567999999998 -55.053830000000005,"
        " -72.26390000000004 -54.49513999999999, -73.28519999999997 -53.95751999999993,"
        " -74.66253 -52.837489999999946, -73.8381 -53.04743000000002,"
        " -72.43417999999997 -53.71539999999999, -71.10773 -54.07432999999992,"
        " -70.59177999999986 -53.61582999999996, -70.26747999999998 -52.93123000000003,"
        " -69.34564999999992 -52.518299999999954, -68.63401022758323 -52.63637045887449)),"
        " ((-69.59042375352405 -17.580011895419332, -69.10024695501949 -18.260125420812678,"
        " -68.96681840684187 -18.981683444904107, -68.44222510443092 -19.40506845467143,"
        " -68.75716712103375 -20.372657972904463, -68.21991309271128 -21.494346612231865,"
        " -67.82817989772273 -22.872918796482175, -67.1066735500636 -22.735924574476417,"
        " -66.9852339341777 -22.98634856536284, -67.32844295924417 -24.02530323659095,"
        " -68.41765296087614 -24.51855478281688, -68.38600114609736 -26.185016371365215,"
        " -68.59479977077268 -26.506908868111296, -68.29554155137043 -26.89933969493578,"
        " -69.00123491074825 -27.52121388113618, -69.65613033718317 -28.459141127233686,"
        " -70.01355038112992 -29.367922865518572, -69.91900834825194 -30.33633920666828,"
        " -70.53506893581951 -31.36501026787031, -70.0743993801536 -33.09120981214805,"
        " -69.81477698431922 -33.273886000299825, -69.81730912950152 -34.1935714657983,"
        " -70.38804948594913 -35.16968759535949, -70.36476925320164 -36.00508879978992,"
        " -71.12188066270987 -36.65812387466232, -71.11862504747549 -37.57682748794724,"
        " -70.81466427273469 -38.55299529394074, -71.41351660834906 -38.91602223079114,"
        " -71.68076127794649 -39.808164157878046, -71.91573401557763 -40.83233936947069,"
        " -71.7468037584155 -42.05138640723598, -72.14889807807856 -42.254888197601375,"
        " -71.91542395698389 -43.40856454851745, -71.46405615913051 -43.787611179378345,"
        " -71.79362260607193 -44.207172133156064, -71.32980078803622 -44.407521661151655,"
        " -71.22277889675976 -44.784242852559416, -71.65931555854536 -44.973688653341426,"
        " -71.55200944689128 -45.5607329241771, -71.91725847033024 -46.88483814879177,"
        " -72.44735531278027 -47.73853281025352, -72.33116085477201 -48.2442383766618,"
        " -72.64824744331494 -48.87861825947683, -73.4154357571201 -49.31843637471297,"
        " -73.32805091011453 -50.378785088909915, -72.97574683296469 -50.741450290734285,"
        " -72.30997351753234 -50.67700977966632, -72.32940385607407 -51.42595631287243,"
        " -71.91480383979638 -52.0090223058659, -69.49836218939609 -52.14276091263727,"
        " -68.57154537624133 -52.299443855346226, -69.46128434922667 -52.29195077266391,"
        " -69.9427795071062 -52.53793059037322, -70.8451016913546 -52.89920052852571,"
        " -71.00633216010525 -53.83325204220132, -71.429794684521 -53.85645476030037,"
        " -72.55794287788488 -53.53141000118449, -73.7027567206629 -52.835069268607235,"
        " -73.7027567206629 -52.835070076051494, -74.94676347522517 -52.262753588419,"
        " -75.2600260077785 -51.62935475037325, -74.97663245308988 -51.0433956846157,"
        " -75.47975419788355 -50.37837167745158, -75.60801510283198 -48.67377288187184,"
        " -75.18276974150216 -47.7119194476232, -74.1265809801047 -46.93925343199511,"
        " -75.64439531116545 -46.64764332457207, -74.69215369332312 -45.76397633238103,"
        " -74.35170935738425 -44.10304412208794, -73.24035600451522 -44.454960625995604,"
        " -72.7178039211798 -42.38335580827898, -73.38889990913822 -42.117532240569574,"
        " -73.70133561877488 -43.365776462579774, -74.33194312203261 -43.22495818458442,"
        " -74.0179571194272 -41.79481292090683, -73.67709937202999 -39.94221282324317,"
        " -73.21759253609065 -39.25868865331856, -73.50555945503712 -38.282882582351114,"
        " -73.58806087919109 -37.15628468195598, -73.1667170884993 -37.12378020604439,"
        " -72.55313696968174 -35.50884002049106, -71.86173214383263 -33.90909270603153,"
        " -71.4384504869299 -32.41889942803078, -71.66872066922247 -30.920644626592495,"
        " -71.37008256700773 -30.09568206148503, -71.48989437527645 -28.861442152625923,"
        " -70.90512386746161 -27.640379734001247, -70.72495398627599 -25.705924167587256,"
        " -70.40396582709502 -23.628996677344574, -70.09124589708074 -21.39331918710126,"
        " -70.16441972520605 -19.756468194256165, -70.37257239447771 -18.34797535570887,"
        " -69.85844356960587 -18.092693780187012, -69.59042375352405 -17.580011895419332)))"
    )
    yield wkt


@pytest.fixture(scope="function")
def feature_properties_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/properties.json"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def feature_fixture(
    projects_fixture, db_session: "sqlalchemy_config.Session"
) -> "Iterator[Feature]":
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/properties.json"), "rb") as f:
        feat = Feature.fromGeoJSON(json.loads(f.read()))
        feat.project_id = projects_fixture.id
        db_session.add(feat)
        db_session.commit()
        yield feat


@pytest.fixture(scope="function")
def image_feature_fixture(
    image_file_fixture, db_session: "sqlalchemy_config.Session"
) -> "Iterator[FeaturesService]":
    yield FeaturesService.fromImage(db_session, 1, image_file_fixture, metadata={})


@pytest.fixture(scope="function")
def import_file_from_tapis_mock():
    with patch(
        "geoapi.tasks.external_data.import_file_from_tapis"
    ) as import_file_from_tapis:
        yield import_file_from_tapis


@pytest.fixture(scope="function")
def import_from_tapis_mock():
    with patch("geoapi.services.projects.import_from_tapis") as mock_import:
        yield mock_import


@pytest.fixture(scope="function")
def convert_to_potree_mock():
    with patch(
        "geoapi.services.point_cloud.convert_to_potree"
    ) as mock_convert_to_potree:

        class FakeAsyncResult:
            id = "b53fdb0a-de1a-11e9-b641-0242c0a80004"

        mock_convert_to_potree.apply_async.return_value = FakeAsyncResult()
        yield mock_convert_to_potree


@pytest.fixture(scope="function")
def check_point_cloud_mock():
    with patch(
        "geoapi.services.point_cloud.check_point_cloud"
    ) as mock_check_point_cloud_mock:
        mock_check_point_cloud_mock.return_value = None
        yield mock_check_point_cloud_mock


@pytest.fixture(scope="function")
def check_point_cloud_mock_missing_crs():
    with patch(
        "geoapi.services.point_cloud.check_point_cloud"
    ) as mock_check_point_cloud_mock:
        mock_check_point_cloud_mock.side_effect = InvalidCoordinateReferenceSystem()
        yield mock_check_point_cloud_mock


@pytest.fixture(scope="function")
def get_point_cloud_info_mock():
    with patch(
        "geoapi.services.point_cloud.get_point_cloud_info"
    ) as mock_get_point_cloud_info:
        mock_result = MagicMock()
        mock_result.get.return_value = [{"name": "test.las"}]

        mock_get_point_cloud_info.return_value = mock_result
        yield mock_get_point_cloud_info


@pytest.fixture(scope="function")
def tapis_file_listings_mock():
    filesListing = [
        TapisFileListing(
            {"path": "/testPath", "type": "dir", "lastModified": "2020-08-31T12:00:00Z"}
        ),
        TapisFileListing(
            {
                "type": "file",
                "path": "/testPath/file.json",
                "lastModified": "2020-08-31T12:00:00Z",
            }
        ),
    ]
    yield filesListing


@pytest.fixture(scope="function")
def tapis_utils_with_geojson_file_mock(tapis_file_listings_mock, geojson_file_fixture):
    with patch("geoapi.services.projects.TapisUtils") as MockTapisUtils:
        MockTapisUtils().listing.return_value = tapis_file_listings_mock
        MockTapisUtils().getFile.return_value = geojson_file_fixture
        MockTapisUtils().systemsGet.return_value = {
            "id": "testSystem",
            "description": "System Description",
            "name": "System Name",
        }
        yield MockTapisUtils()


@pytest.fixture(scope="function")
def get_system_users_mock(
    userdata,
    db_session: "sqlalchemy_config.Session",
) -> "Iterator[MagicMock]":
    u1 = db_session.get(User, 1)
    u2 = db_session.get(User, 2)
    users = [
        SystemUser(username=u2.username, admin=False),
        SystemUser(username=u1.username, admin=True),
    ]
    with patch(
        "geoapi.services.projects.get_system_users", return_value=users
    ) as get_system_users:
        yield get_system_users


@pytest.fixture(scope="function")
def remove_project_assets_mock():
    # we mock method so that we execute it synchronously (and not as a celery task on worker)
    # when testing some routes
    with patch("geoapi.services.projects.remove_project_assets") as mock_remove_project:
        from geoapi.tasks.projects import remove_project_assets

        def remove(args):
            remove_project_assets(project_id=args[0])

        mock_remove_project.apply_async.side_effect = remove
        yield mock_remove_project


@pytest.fixture(scope="function")
def tile_server_ini_file_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/metadata.ini"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def questionnaire_file_without_assets_fixture():
    home = os.path.dirname(__file__)
    filename = "fixtures/questionnaire_without_assets.rq"
    with open(os.path.join(home, filename), "rb") as f:
        f.filename = filename
        yield f


@pytest.fixture(scope="function")
def questionnaire_file_with_assets_fixture():
    home = os.path.dirname(__file__)
    filename = "fixtures/questionnaire_with_assets.rqa/questionnaire_with_assets.rq"
    with open(os.path.join(home, filename), "rb") as f:
        f.filename = filename
        yield f


@pytest.fixture(scope="function")
def tapis_metadata_with_geolocation():
    home = os.path.dirname(__file__)
    with open(
        os.path.join(home, "fixtures/tapis_meta_with_geolocation.json"), "rb"
    ) as f:
        yield json.loads(f.read())


@pytest.fixture(scope="function")
def tapis_metadata_without_geolocation():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/tapis_meta_no_geolocation.json"), "rb") as f:
        yield json.loads(f.read())
