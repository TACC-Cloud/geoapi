from unittest.mock import patch
import pytest
import os

from geoapi.models import User, Feature
from geoapi.db import db_session
from geoapi.tasks.external_data import (import_from_agave,
                                        import_point_clouds_from_agave,
                                        refresh_observable_projects,
                                        get_additional_files)
from geoapi.utils.agave import AgaveFileListing
from geoapi.utils.assets import get_project_asset_dir, get_asset_path
from geoapi.exceptions import InvalidCoordinateReferenceSystem
from geoapi.services.point_cloud import PointCloudService


@pytest.fixture(scope="function")
def rollback_side_effect():
    with patch('geoapi.db.db_session.rollback', side_effect=db_session.rollback) as rollback:
        yield rollback


@pytest.fixture(scope="function")
def db_session_commit_throws_exception():
    with patch('geoapi.db.db_session.commit', side_effect=Exception) as commit:
        yield commit


@pytest.fixture(scope="function")
def agave_utils_with_geojson_file(geojson_file_fixture):
    with patch('geoapi.tasks.external_data.AgaveUtils') as MockAgaveUtils:
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
        MockAgaveUtils().listing.return_value = filesListing
        MockAgaveUtils().getFile.return_value = geojson_file_fixture
        yield MockAgaveUtils()


@pytest.mark.worker
def test_external_data_good_files(userdata, projects_fixture, agave_utils_with_geojson_file):
    u1 = db_session.query(User).filter(User.username == "test1").first()

    import_from_agave(u1.id, "testSystem", "/testPath", projects_fixture.id)
    features = db_session.query(Feature).all()
    # the test geojson has 3 features in it
    assert len(features) == 3
    # This should only have been called once, since there is only
    # one FILE in the listing
    agave_utils_with_geojson_file.getFile.assert_called_once()


@pytest.mark.worker
@patch("geoapi.tasks.external_data.AgaveUtils")
def test_import_point_clouds_from_agave(MockAgaveUtils,
                                        projects_fixture,
                                        point_cloud_fixture,
                                        lidar_las1pt2_file_fixture):
    MockAgaveUtils().getFile.return_value = lidar_las1pt2_file_fixture

    u1 = db_session.query(User).get(1)
    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_agave(u1.id, files, point_cloud_fixture.id)

    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FINISHED"
    assert point_cloud.task.description == ""
    assert len(os.listdir(get_project_asset_dir(point_cloud.project_id))) == 2
    assert len(os.listdir(
        get_asset_path(point_cloud.feature.assets[0].path))) == 5  # index.html, preview.html, pointclouds, libs, logo
    assert len(os.listdir(get_asset_path(point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR))) == 1


@pytest.mark.worker
@patch("geoapi.tasks.external_data.check_point_cloud")
@patch("geoapi.tasks.external_data.AgaveUtils")
def test_import_point_clouds_from_agave_check_point_cloud_missing_crs(MockAgaveUtils,
                                                                      check_mock,
                                                                      projects_fixture,
                                                                      point_cloud_fixture,
                                                                      lidar_las1pt2_file_fixture):
    MockAgaveUtils().getFile.return_value = lidar_las1pt2_file_fixture
    check_mock.apply.side_effect = InvalidCoordinateReferenceSystem()

    u1 = db_session.query(User).get(1)
    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_agave(u1.id, files, point_cloud_fixture.id)

    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FAILED"
    assert point_cloud.task.description == "Error importing file1.las: missing coordinate reference system"
    assert len(os.listdir(get_asset_path(point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR))) == 0


@pytest.mark.worker
@patch("geoapi.tasks.external_data.check_point_cloud")
@patch("geoapi.tasks.external_data.AgaveUtils")
def test_import_point_clouds_from_agave_check_point_cloud_unknown(MockAgaveUtils,
                                                                  check_mock,
                                                                  projects_fixture,
                                                                  point_cloud_fixture,
                                                                  lidar_las1pt2_file_fixture):
    MockAgaveUtils().getFile.return_value = lidar_las1pt2_file_fixture
    check_mock.apply.side_effect = Exception("dummy")

    u1 = db_session.query(User).get(1)
    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_agave(u1.id, files, point_cloud_fixture.id)

    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FAILED"
    assert point_cloud.task.description == "Unknown error importing designsafe.storage.default:file1.las"
    assert len(os.listdir(get_asset_path(point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR))) == 0


@pytest.mark.worker
@patch("geoapi.tasks.external_data.convert_to_potree")
@patch("geoapi.tasks.external_data.AgaveUtils")
def test_import_point_clouds_from_agave_conversion_error(MockAgaveUtils,
                                                         convert_mock,
                                                         projects_fixture,
                                                         point_cloud_fixture,
                                                         lidar_las1pt2_file_fixture):
    MockAgaveUtils().getFile.return_value = lidar_las1pt2_file_fixture
    convert_mock.apply.side_effect = Exception("dummy")

    u1 = db_session.query(User).get(1)
    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_agave(u1.id, files, point_cloud_fixture.id)

    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FAILED"
    assert point_cloud.task.description == ""
    assert len(os.listdir(get_asset_path(point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR))) == 1


@pytest.mark.worker
@patch("geoapi.tasks.external_data.AgaveUtils")
def test_import_point_clouds_failed_dbsession_rollback(MockAgaveUtils,
                                                       projects_fixture,
                                                       point_cloud_fixture,
                                                       lidar_las1pt2_file_fixture,
                                                       db_session_commit_throws_exception,
                                                       rollback_side_effect):
    MockAgaveUtils().getFile.return_value = lidar_las1pt2_file_fixture

    u1 = db_session.query(User).get(1)
    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]

    with pytest.raises(Exception):
        import_point_clouds_from_agave(u1.id, files, point_cloud_fixture.id)

    rollback_side_effect.assert_called_once()


@pytest.mark.worker
def test_import_from_agave_failed_dbsession_rollback(agave_utils_with_geojson_file,
                                                     userdata,
                                                     projects_fixture,
                                                     db_session_commit_throws_exception,
                                                     rollback_side_effect):
    with pytest.raises(Exception):
        import_from_agave(userdata.id, "testSystem", "/testPath", projects_fixture.id)

    rollback_side_effect.assert_called()


@pytest.mark.worker
def test_refresh_observable_projects_dbsession_rollback(agave_utils_with_geojson_file,
                                                        observable_projects_fixture,
                                                        db_session_commit_throws_exception,
                                                        rollback_side_effect):
    refresh_observable_projects()
    rollback_side_effect.assert_called()


def test_get_additional_files_none(agave_utils_with_geojson_file):
    assert not get_additional_files("testSystem", "/testPath/file.jpg", agave_utils_with_geojson_file)


def test_get_additional_files(agave_utils_with_geojson_file):
    files = get_additional_files("testSystem", "/testPath/file.shp", agave_utils_with_geojson_file)
    assert len(files) == 14


def test_get_additional_files_with_available_files(agave_utils_with_geojson_file):
    available_files = ["/testPath/file.shx",
                       "/testPath/file.dbf",
                       "/testPath/file.sbn",
                       "/testPath/file.sbx",
                       "/testPath/file.fbn",
                       "/testPath/file.fbx",
                       "/testPath/file.ain",
                       "/testPath/file.aih",
                       "/testPath/file.atx",
                       "/testPath/file.ixs",
                       "/testPath/file.mxs",
                       "/testPath/file.prj",
                       "/testPath/file.xml",
                       "/testPath/file.cpg"]
    files = get_additional_files("testSystem",
                                 "/testPath/file.shp",
                                 agave_utils_with_geojson_file,
                                 available_files=available_files)
    assert len(files) == 14

    available_files = ["/testPath/file.shx",
                       "/testPath/file.dbf",
                       "/testPath/file.prj"]
    files = get_additional_files("testSystem",
                                 "/testPath/file.shp",
                                 agave_utils_with_geojson_file,
                                 available_files=available_files)
    assert len(files) == 3


def test_get_additional_files_but_missing_prj(agave_utils_with_geojson_file):
    available_files_missing_prj = ["/testPath/file.shx", "/testPath/file.dbf"]
    with pytest.raises(Exception):
        get_additional_files("testSystem",
                             "/testPath/file.shp",
                             agave_utils_with_geojson_file,
                             available_files=available_files_missing_prj)
