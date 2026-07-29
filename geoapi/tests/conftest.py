import os

# Suppress Litestar warnings about synchronous route handlers during tests.
# TestClient runs synchronously anyway, so these warnings are not actionable in test context.
os.environ["LITESTAR_WARN_IMPLICIT_SYNC_TO_THREAD"] = "0"

# flake8: noqa: E402 (module imports after env setup)
import pytest
import json
import tempfile
import shutil
import laspy
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage
from typing import TYPE_CHECKING
from collections.abc import Iterator
from litestar.testing import TestClient
from geoapi.db import Base, litestar_sqlalchemy_config as sqlalchemy_config
from geoapi.models import TaskStatus
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
from geoapi import settings

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
def test_client_anonymous_session() -> "Iterator[TestClient[Litestar]]":
    """Test client with session and CSRF token, but no authenticated user.

    Use for testing auth layer responses (401) without CSRF blocking.
    """
    with TestClient(app=app, session_config=session_auth_config) as client:
        client.set_session_data({})

        # Get CSRF cookie
        client.get("/projects/")
        csrf_token = client.cookies.get(f"csrftoken-{settings.APP_ENV}")

        if csrf_token:
            client.headers[f"x-csrftoken-{settings.APP_ENV}"] = csrf_token

        yield client


@pytest.fixture(scope="function")
def test_client_user1() -> "Iterator[TestClient[Litestar]]":
    """Test client authenticated as user1 via session."""
    with TestClient(app=app, session_config=session_auth_config) as client:
        client.set_session_data({"username": "test1", "tenant": "test"})
        yield client


@pytest.fixture(scope="function")
def test_client_user2() -> "Iterator[TestClient[Litestar]]":
    """Test client authenticated as user2 via session."""
    with TestClient(app=app, session_config=session_auth_config) as client:
        client.set_session_data({"username": "test2", "tenant": "test"})
        yield client


@pytest.fixture(scope="function")
def test_client() -> "Iterator[TestClient[Litestar]]":
    """Test client with no session or auth.

    Use for JWT auth tests by passing X-Tapis-Token header manually.
    """
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


@pytest.fixture(scope="function")
def mock_task_update_webhook(requests_mock):
    """Mock the Celery->Litestar webhook."""
    requests_mock.post(
        "http://test:8888/webhooks/task-update",
        json={"ok": True},
        status_code=200,
    )
    yield requests_mock


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
def task_fixture(
    db_session: "sqlalchemy_config.Session", projects_fixture
) -> "Iterator[Task]":
    task = Task(
        process_id="some-process-id",
        project_id=projects_fixture.id,
        status=TaskStatus.COMPLETED,
        description="description",
    )
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
def raster_singleband_int16_m30dem():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/rasters/m30dem.tif"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def raster_singleband_byte_SP27GTIF():
    # raster in state plane (Illinois East, NAD27)
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/rasters/SP27GTIF.tiff"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def raster_singleband_byte_UTM2GTIF():
    # raster in UTM zone 16N
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/rasters/UTM2GTIF.tiff"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def raster_threeband_byte_rgbsmall():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/rasters/rgbsmall.tif"), "rb") as f:
        yield f


@pytest.fixture(scope="function")
def raster_threeband_byte_orthodrone_center100():
    # cropped 100x100 window from the center of Ortho-DroneMapper.tif (red rocks)
    # 4 bands: rgb + alpha
    home = os.path.dirname(__file__)
    with open(
        os.path.join(home, "fixtures/rasters/Ortho-DroneMapper_center100.tif"), "rb"
    ) as f:
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
def point_and_polygon_geojson_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/TACC_point_and_polygon.geojson"), "rb") as f:
        yield FileStorage(f, filename="TACC_point_and_polygon.geojson")


@pytest.fixture(scope="function")
def points_1000_geojson_path_fixture():
    """Path to a GeoJSON of 1000 points scattered globally (EPSG:4326)."""
    home = os.path.dirname(__file__)
    return os.path.join(home, "fixtures/1000_points.geojson")


@pytest.fixture(scope="function")
def shapefile_additional_files_fixture():
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/shapefile.cpg"), "rb") as cpg, open(
        os.path.join(home, "fixtures/shapefile.dbf"), "rb"
    ) as dbf, open(os.path.join(home, "fixtures/shapefile.prj"), "rb") as prj, open(
        os.path.join(home, "fixtures/shapefile.shx"), "rb"
    ) as shx:
        yield [FileStorage(cpg), FileStorage(dbf), FileStorage(prj), FileStorage(shx)]


@pytest.fixture(scope="function")
def shapefile_large_extent_fixture():
    """A world-scale shapefile (country polygons, incl. an antimeridian-spanning
    one) -- the pathological large-extent case. Tiling it is very slow, so use it
    only for read/convert-level checks, not full ingest."""
    home = os.path.dirname(__file__)
    with open(os.path.join(home, "fixtures/shapefile_large_extent.shp"), "rb") as f:
        yield FileStorage(f)


@pytest.fixture(scope="function")
def shapefile_large_extent_additional_files_fixture():
    home = os.path.dirname(__file__)
    prefix = "fixtures/shapefile_large_extent"
    with open(os.path.join(home, f"{prefix}.cpg"), "rb") as cpg, open(
        os.path.join(home, f"{prefix}.dbf"), "rb"
    ) as dbf, open(os.path.join(home, f"{prefix}.prj"), "rb") as prj, open(
        os.path.join(home, f"{prefix}.shx"), "rb"
    ) as shx:
        yield [FileStorage(cpg), FileStorage(dbf), FileStorage(prj), FileStorage(shx)]


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
    image_file_fixture,
    db_session: "sqlalchemy_config.Session",
    projects_fixture,
) -> Feature:
    yield FeaturesService.fromImage(
        db_session,
        projects_fixture.id,
        image_file_fixture,
        metadata={},
        original_system="system",
        original_path="original/path.jpg",
    )


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
    with patch("geoapi.tasks.point_cloud.convert_to_potree") as mock_convert_to_potree:

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
