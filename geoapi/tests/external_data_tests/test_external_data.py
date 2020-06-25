from unittest.mock import patch
import pytest
import os

from geoapi.models import User, Project, Feature
from geoapi.db import db_session
from geoapi.tasks.external_data import import_from_agave, import_point_clouds_from_agave
from geoapi.utils.agave import AgaveFileListing
from geoapi.utils.assets import get_project_asset_dir, get_asset_path
from geoapi.exceptions import InvalidCoordinateReferenceSystem
from geoapi.services.point_cloud import PointCloudService


@patch("geoapi.tasks.external_data.AgaveUtils")
def test_external_data_good_files(MockAgaveUtils, userdata, projects_fixture, geojson_file_fixture):
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
    u1 = db_session.query(User).filter(User.username == "test1").first()
    proj = db_session.query(Project).get(1)
    MockAgaveUtils().listing.return_value = filesListing
    MockAgaveUtils().getFile.return_value = geojson_file_fixture
    import_from_agave(u1.id, "testSystem", "/testPath", proj.id)
    features = db_session.query(Feature).all()
    # the test geojson has 3 features in it
    assert len(features) == 3
    # This should only have been called once, since there is only
    # one FILE in the listing
    assert MockAgaveUtils().getFile.called_once()


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