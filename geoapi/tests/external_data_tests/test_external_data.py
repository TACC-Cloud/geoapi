from unittest.mock import patch
import pytest
import os
import re
import subprocess

from geoapi.models import Feature, ImportedFile
from geoapi.db import db_session, create_task_session
from geoapi.tasks.external_data import (
    import_from_tapis,
    import_point_clouds_from_tapis,
    refresh_projects_watch_content,
    refresh_projects_watch_users,
    get_additional_files,
)
from geoapi.utils.features import is_member_of_rapp_project_folder
from geoapi.utils.external_apis import TapisFileListing, SystemUser
from geoapi.utils.assets import get_project_asset_dir, get_asset_path
from geoapi.exceptions import InvalidCoordinateReferenceSystem
from geoapi.services.point_cloud import PointCloudService


METADATA_ROUTE = re.compile(r"https://.*/api/filemeta/.*/.*")


@pytest.fixture(scope="function")
def metadata_none_fixture(requests_mock):
    response = {}
    requests_mock.get(METADATA_ROUTE, json=response)


@pytest.fixture(scope="function")
def metadata_but_no_geolocation_fixture(requests_mock):
    response = {"value": {"geolocation": []}}
    requests_mock.get(METADATA_ROUTE, json=response)


@pytest.fixture(scope="function")
def metadata_geolocation_30long_20lat_fixture(requests_mock):
    response = {"value": {"geolocation": [{"longitude": 20, "latitude": 30}]}}
    requests_mock.get(METADATA_ROUTE, json=response)


@pytest.fixture(scope="function")
def get_system_users_mock(user1, user2):
    users = [
        SystemUser(username=user1.username, admin=True),
        SystemUser(username=user2.username, admin=False),
    ]
    with patch(
        "geoapi.tasks.external_data.get_system_users", return_value=users
    ) as get_system_users:
        yield get_system_users


@pytest.fixture(scope="function")
def task_session_commit_throws_exception():
    # Create a real session object
    real_session = create_task_session().__enter__()

    with patch("geoapi.db.sessionmaker") as mock_create_task_session:
        # Patch the commit method of the real session
        with patch.object(real_session, "commit") as mock_commit:
            mock_create_task_session.return_value.return_value = real_session
            mock_commit.side_effect = Exception("Session commit failed")
            yield real_session
    real_session.__exit__(None, None, None)  # Ensure __exit__ is called


@pytest.fixture(scope="function")
def tapis_utils_with_geojson_file(geojson_file_fixture):
    with patch("geoapi.tasks.external_data.TapisUtils") as MockTapisUtils:
        with patch("geoapi.utils.external_apis.TapisUtils") as MockTapisUtilsInUtils:
            filesListing = [
                TapisFileListing(
                    {
                        "type": "file",
                        "path": "/testPath/file.json",
                        "lastModified": "2020-08-31T12:00:00Z",
                    }
                )
            ]
            MockTapisUtils().listing.return_value = filesListing
            MockTapisUtils().getFile.return_value = geojson_file_fixture
            MockTapisUtilsInUtils().listing.return_value = filesListing
            MockTapisUtilsInUtils().getFile.return_value = geojson_file_fixture
            yield MockTapisUtils()


@pytest.fixture(scope="function")
def tapis_utils_with_bad_image_file(image_file_no_location_fixture):
    with patch("geoapi.tasks.external_data.TapisUtils") as MockTapisUtils:
        with patch("geoapi.utils.external_apis.TapisUtils") as MockTapisUtilsInUtils:
            filesListing = [
                TapisFileListing(
                    {
                        "type": "file",
                        "path": "/testPath/file_no_location_data.jpg",
                        "lastModified": "2020-08-31T12:00:00Z",
                    }
                )
            ]
            MockTapisUtils().listing.return_value = filesListing
            MockTapisUtils().getFile.return_value = image_file_no_location_fixture
            MockTapisUtilsInUtils().listing.return_value = filesListing
            MockTapisUtilsInUtils().getFile.return_value = (
                image_file_no_location_fixture
            )

            class MockTapis:
                client_in_utils = MockTapisUtilsInUtils()
                client_in_external_data = MockTapisUtils()

            yield MockTapis


@pytest.fixture(scope="function")
def tapis_utils_with_image_file_from_rapp_folder(
    metadata_geolocation_30long_20lat_fixture, requests_mock, image_file_fixture
):
    filesListing = [
        TapisFileListing(
            {
                "type": "file",
                "path": "/RApp/file.jpg",
                "lastModified": "2020-08-31T12:00:00Z",
            }
        )
    ]

    with patch(
        "geoapi.utils.external_apis.TapisUtils.listing"
    ) as mock_listing_utils, patch(
        "geoapi.utils.external_apis.TapisUtils.getFile"
    ) as mock_get_file_utils, patch(
        "geoapi.tasks.external_data.TapisUtils.listing"
    ) as mock_listing_external_data, patch(
        "geoapi.tasks.external_data.TapisUtils.getFile"
    ) as mock_get_file_external_data:
        mock_listing_utils.return_value = filesListing
        mock_get_file_utils.return_value = image_file_fixture
        mock_listing_external_data.return_value = filesListing
        mock_get_file_external_data.return_value = image_file_fixture

        class MockTapis:
            listing_utils = mock_listing_utils
            get_file_utils = mock_get_file_utils
            listing_external_data = mock_listing_external_data
            get_file_external_data = mock_get_file_external_data

        yield MockTapis


@pytest.fixture(scope="function")
def tapis_utils_listing_with_single_trash_folder_of_image(image_file_fixture):
    """
    Creates a file listing for a single .Trash folder with a file in it:
    * /
    *   .Trash/
    *          file.jpg
    """

    top_level_file_listing = [
        TapisFileListing(
            {"path": ".Trash", "type": "dir", "lastModified": "2020-08-31T12:00:00Z"}
        )
    ]
    subfolder_file_listing = [
        TapisFileListing(
            {
                "type": "file",
                "path": ".Trash/file.jpg",
                "lastModified": "2020-08-31T12:00:00Z",
            }
        )
    ]
    with patch("geoapi.utils.external_apis.TapisUtils") as MockTapisUtilsInUtils:
        MockTapisUtilsInUtils().listing.side_effect = [
            top_level_file_listing,
            subfolder_file_listing,
        ]
        MockTapisUtilsInUtils().getFile.return_value = image_file_fixture
        with patch("geoapi.tasks.external_data.TapisUtils") as MockTapisUtils:
            MockTapisUtils().listing.side_effect = [
                top_level_file_listing,
                subfolder_file_listing,
            ]
            MockTapisUtils().getFile.return_value = image_file_fixture

            class MockTapis:
                client_in_utils = MockTapisUtilsInUtils()
                client_in_external_data = MockTapisUtils()

            yield MockTapis


@pytest.mark.worker
def test_external_data_good_files(
    metadata_geolocation_30long_20lat_fixture,
    user1,
    projects_fixture,
    tapis_utils_with_geojson_file,
):
    import_from_tapis(
        projects_fixture.tenant_id,
        user1.id,
        "testSystem",
        "/testPath",
        projects_fixture.id,
    )
    features = db_session.query(Feature).all()
    # the test geojson has 3 features in it
    assert len(features) == 3
    imported_file = db_session.query(ImportedFile).first()
    assert imported_file.successful_import

    # This should only have been called once, since there is only
    # one FILE in the listing
    tapis_utils_with_geojson_file.getFile.assert_called_once()

    tapis_utils_with_geojson_file.reset_mock()

    # run import again (to mimic the periodically scheduled refresh_projects_watch_content)
    import_from_tapis(
        projects_fixture.tenant_id,
        user1.id,
        "testSystem",
        "/testPath",
        projects_fixture.id,
    )
    # This should only have been called once, since there is only
    # one FILE in the listing
    tapis_utils_with_geojson_file.getFile.assert_not_called()


@pytest.mark.worker
def test_external_data_bad_files(
    metadata_none_fixture, user1, projects_fixture, tapis_utils_with_bad_image_file
):
    import_from_tapis(
        projects_fixture.tenant_id,
        user1.id,
        "testSystem",
        "/testPath",
        projects_fixture.id,
    )
    features = db_session.query(Feature).all()
    assert len(features) == 0
    assert not os.path.exists(get_project_asset_dir(projects_fixture.id))
    tapis_utils_with_bad_image_file.client_in_external_data.getFile.assert_called_once()
    imported_file = db_session.query(ImportedFile).first()
    assert not imported_file.successful_import

    tapis_utils_with_bad_image_file.client_in_external_data.reset_mock()

    # run import again (to mimic the periodically scheduled refresh_projects_watch_content)
    import_from_tapis(
        projects_fixture.tenant_id,
        user1.id,
        "testSystem",
        "/testPath",
        projects_fixture.id,
    )
    # Getting the file should only have been called once, since there is only
    # one FILE in the listing, and we already attempted to import it in the first call
    # to import_from_tapis
    tapis_utils_with_bad_image_file.client_in_external_data.getFile.assert_not_called()


@pytest.mark.worker
def test_external_data_no_files_except_for_trash(
    user1, projects_fixture, tapis_utils_listing_with_single_trash_folder_of_image
):
    import_from_tapis(
        projects_fixture.tenant_id, user1.id, "testSystem", "/", projects_fixture.id
    )

    features = db_session.query(Feature).all()
    # just a .Trash dir so nothing to import and only top level listing should occur
    assert len(features) == 0
    assert (
        tapis_utils_listing_with_single_trash_folder_of_image.client_in_external_data.listing.call_count
        == 1
    )
    tapis_utils_listing_with_single_trash_folder_of_image.client_in_external_data.getFile.assert_not_called()
    tapis_utils_listing_with_single_trash_folder_of_image.client_in_utils.getFile.assert_not_called()


@pytest.mark.worker
def test_external_data_rapp(
    user1, projects_fixture, tapis_utils_with_image_file_from_rapp_folder
):
    import_from_tapis(
        projects_fixture.tenant_id, user1.id, "testSystem", "/Rapp", projects_fixture.id
    )
    features = db_session.query(Feature).all()
    # should be one feature with a single image asset
    assert len(features) == 1
    assert len(features[0].assets) == 1
    assert (
        len(os.listdir(get_project_asset_dir(features[0].project_id))) == 2
    )  # processed image + thumbnail
    # This should only have been called once, since there is only one FILE in the listing
    tapis_utils_with_image_file_from_rapp_folder.get_file_external_data.assert_called_once()


@pytest.mark.worker
def test_external_data_rapp_missing_geospatial_metadata(
    user1,
    projects_fixture,
    tapis_utils_with_image_file_from_rapp_folder,
    metadata_but_no_geolocation_fixture,
):
    import_from_tapis(
        projects_fixture.tenant_id, user1.id, "testSystem", "/Rapp", projects_fixture.id
    )
    features = db_session.query(Feature).all()
    assert len(features) == 0


@pytest.mark.worker
@patch("geoapi.tasks.external_data.TapisUtils")
def test_import_point_clouds_from_tapis(
    MockTapisUtils,
    user1,
    projects_fixture,
    point_cloud_fixture,
    lidar_las1pt2_file_fixture,
):
    MockTapisUtils().getFile.return_value = lidar_las1pt2_file_fixture

    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_tapis(user1.id, files, point_cloud_fixture.id)

    db_session.refresh(point_cloud_fixture)
    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FINISHED"
    assert point_cloud.task.description == ""
    assert len(os.listdir(get_project_asset_dir(point_cloud.project_id))) == 2
    assert (
        len(os.listdir(get_asset_path(point_cloud.feature.assets[0].path))) == 5
    )  # index.html, preview.html, pointclouds, libs, logo
    assert (
        len(
            os.listdir(
                get_asset_path(
                    point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR
                )
            )
        )
        == 1
    )
    assert os.path.isfile(
        os.path.join(get_asset_path(point_cloud.feature.assets[0].path), "index.html")
    )
    with open(
        os.path.join(get_asset_path(point_cloud.feature.assets[0].path), "index.html"),
        "r+",
    ) as f:
        index = f.read()
        assert "nsf_logo" in index
    assert os.path.isfile(
        os.path.join(get_asset_path(point_cloud.feature.assets[0].path), "preview.html")
    )
    with open(
        os.path.join(
            get_asset_path(point_cloud.feature.assets[0].path), "preview.html"
        ),
        "r+",
    ) as f:
        preview = f.read()
        assert "nsf_logo" not in preview
        assert "$('.potree_menu_toggle').hide()" in preview


@pytest.mark.worker
@patch("geoapi.tasks.external_data.check_point_cloud")
@patch("geoapi.tasks.external_data.TapisUtils")
def test_import_point_clouds_from_tapis_check_point_cloud_missing_crs(
    MockTapisUtils,
    check_mock,
    user1,
    projects_fixture,
    point_cloud_fixture,
    lidar_las1pt2_file_fixture,
):
    MockTapisUtils().getFile.return_value = lidar_las1pt2_file_fixture
    check_mock.side_effect = InvalidCoordinateReferenceSystem()

    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_tapis(user1.id, files, point_cloud_fixture.id)

    db_session.refresh(point_cloud_fixture)
    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FAILED"
    assert (
        point_cloud.task.description
        == "Error importing file1.las: missing coordinate reference system"
    )
    assert (
        len(
            os.listdir(
                get_asset_path(point_cloud.path, PointCloudService.ORIGINAL_FILES_DIR)
            )
        )
        == 0
    )


@pytest.mark.worker
@patch("geoapi.tasks.external_data.check_point_cloud")
@patch("geoapi.tasks.external_data.TapisUtils")
def test_import_point_clouds_from_tapis_check_point_cloud_unknown(
    MockTapisUtils,
    check_mock,
    user1,
    projects_fixture,
    point_cloud_fixture,
    lidar_las1pt2_file_fixture,
):
    MockTapisUtils().getFile.return_value = lidar_las1pt2_file_fixture
    check_mock.side_effect = Exception("dummy")

    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_tapis(user1.id, files, point_cloud_fixture.id)

    db_session.refresh(point_cloud_fixture)
    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FAILED"
    assert (
        point_cloud.task.description
        == "Unknown error importing designsafe.storage.default:file1.las"
    )
    assert (
        len(
            os.listdir(
                get_asset_path(
                    point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR
                )
            )
        )
        == 0
    )


@pytest.mark.worker
@patch("geoapi.tasks.external_data.convert_to_potree")
@patch("geoapi.tasks.external_data.TapisUtils")
def test_import_point_clouds_from_tapis_conversion_error(
    MockTapisUtils,
    convert_mock,
    user1,
    projects_fixture,
    point_cloud_fixture,
    lidar_las1pt2_file_fixture,
):
    MockTapisUtils().getFile.return_value = lidar_las1pt2_file_fixture
    convert_mock.side_effect = Exception("dummy")

    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_tapis(user1.id, files, point_cloud_fixture.id)

    db_session.refresh(point_cloud_fixture)
    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FAILED"
    assert point_cloud.task.description == "Unknown error occurred"
    assert (
        len(
            os.listdir(
                get_asset_path(
                    point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR
                )
            )
        )
        == 1
    )


@pytest.mark.worker
@patch("geoapi.tasks.external_data.TapisUtils")
@patch("geoapi.tasks.lidar.run_potree_converter")
def test_import_point_clouds_from_tapis_conversion_error_due_to_memory_sigterm(
    mock_run_potree_converter,
    MockTapisUtils,
    user1,
    projects_fixture,
    point_cloud_fixture,
    lidar_las1pt2_file_fixture,
):
    MockTapisUtils().getFile.return_value = lidar_las1pt2_file_fixture

    # Mock subprocess.run to raise CalledProcessError with returncode -9 (SIGKILL)
    mock_run_potree_converter.side_effect = subprocess.CalledProcessError(
        returncode=-9,
        cmd=[
            "/opt/PotreeConverter/build/PotreeConverter",
            "--verbose",
            "-i",
            "/path/to/input",
            "-o",
            "/path/to/output",
        ],
    )

    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]
    import_point_clouds_from_tapis(user1.id, files, point_cloud_fixture.id)

    db_session.refresh(point_cloud_fixture)
    point_cloud = point_cloud_fixture
    assert point_cloud.task.status == "FAILED"
    assert (
        point_cloud.task.description
        == "Point cloud conversion failed; process killed due to insufficient memory"
    )
    assert (
        len(
            os.listdir(
                get_asset_path(
                    point_cloud_fixture.path, PointCloudService.ORIGINAL_FILES_DIR
                )
            )
        )
        == 1
    )


@pytest.mark.worker
@patch("geoapi.tasks.external_data.TapisUtils")
def test_import_point_clouds_failed_dbsession_rollback(
    MockTapisUtils,
    user1,
    projects_fixture,
    point_cloud_fixture,
    lidar_las1pt2_file_fixture,
    task_session_commit_throws_exception,
    caplog,
):
    MockTapisUtils().getFile.return_value = lidar_las1pt2_file_fixture

    files = [{"system": "designsafe.storage.default", "path": "file1.las"}]

    with pytest.raises(Exception):
        import_point_clouds_from_tapis(user1.id, files, point_cloud_fixture.id)

    assert "rollback" in caplog.text


@pytest.mark.worker
def test_import_from_tapis_failed_dbsession_rollback(
    tapis_utils_with_geojson_file,
    user1,
    projects_fixture,
    task_session_commit_throws_exception,
    caplog,
):
    with pytest.raises(Exception):
        import_from_tapis(
            projects_fixture.tenant_id,
            user1.id,
            "testSystem",
            "/testPath",
            projects_fixture.id,
        )
    assert "rollback" in caplog.text


@pytest.mark.worker
def test_refresh_projects_watch_users(
    metadata_but_no_geolocation_fixture,
    user1,
    user2,
    tapis_utils_with_geojson_file,
    watch_content_users_projects_fixture,
    get_system_users_mock,
    caplog,
):
    assert len(watch_content_users_projects_fixture.project_users) == 1
    # single user with no admin but is creator
    assert [(user1.username, False, True)] == [
        (u.user.username, u.admin, u.creator)
        for u in watch_content_users_projects_fixture.project_users
    ]

    refresh_projects_watch_users()

    db_session.refresh(watch_content_users_projects_fixture)

    assert "rollback" not in caplog.text

    # now two users with one being the admin and creator
    assert [(user1.username, True, True), (user2.username, False, False)] == [
        (u.user.username, u.admin, u.creator)
        for u in watch_content_users_projects_fixture.project_users
    ]


@pytest.mark.worker
def test_refresh_projects_watch_content(
    metadata_but_no_geolocation_fixture,
    tapis_utils_with_geojson_file,
    watch_content_users_projects_fixture,
    get_system_users_mock,
    caplog,
):
    refresh_projects_watch_content()

    db_session.refresh(watch_content_users_projects_fixture)

    assert "rollback" not in caplog.text
    features = db_session.query(Feature).all()
    # the test geojson has 3 features in it
    assert len(features) == 3


@pytest.mark.worker
def test_refresh_projects_watch_content_dbsession_rollback(
    tapis_utils_with_geojson_file,
    watch_content_users_projects_fixture,
    get_system_users_mock,
    task_session_commit_throws_exception,
    caplog,
):
    refresh_projects_watch_content()
    assert "rollback" in caplog.text


def test_is_member_of_rapp_project_folder():
    assert is_member_of_rapp_project_folder("/bar/RApp/foo.jpg")
    assert is_member_of_rapp_project_folder("/bar/RApp/foo.jpg")
    assert is_member_of_rapp_project_folder("/bar/RApp/bar/foo.jpg")
    assert is_member_of_rapp_project_folder("/RApp/bar/foo.jpg")
    assert not is_member_of_rapp_project_folder("/something/test.jpg")


def test_get_additional_files_none(shapefile_fixture, tapis_utils_with_geojson_file):
    assert not get_additional_files(
        shapefile_fixture,
        "testSystem",
        "/testPath/file.jpg",
        tapis_utils_with_geojson_file,
    )


def test_get_additional_files_shapefiles(
    shapefile_fixture, tapis_utils_with_geojson_file
):
    files = get_additional_files(
        shapefile_fixture,
        "testSystem",
        "/testPath/file.shp",
        tapis_utils_with_geojson_file,
    )
    assert len(files) == 14


def test_get_additional_files_shapefiles_with_available_files(
    shapefile_fixture, tapis_utils_with_geojson_file
):
    available_files = [
        "/testPath/file.shx",
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
        "/testPath/file.cpg",
    ]
    files = get_additional_files(
        shapefile_fixture,
        "testSystem",
        "/testPath/file.shp",
        tapis_utils_with_geojson_file,
        available_files=available_files,
    )
    assert len(files) == 14

    available_files = ["/testPath/file.shx", "/testPath/file.dbf", "/testPath/file.prj"]
    files = get_additional_files(
        shapefile_fixture,
        "testSystem",
        "/testPath/file.shp",
        tapis_utils_with_geojson_file,
        available_files=available_files,
    )
    assert len(files) == 3


def test_get_additional_files_shapefiles_missing_prj(
    shapefile_fixture, tapis_utils_with_geojson_file
):
    available_files_missing_prj = ["/testPath/file.shx", "/testPath/file.dbf"]
    with pytest.raises(Exception):
        get_additional_files(
            shapefile_fixture,
            "testSystem",
            "/testPath/file.shp",
            tapis_utils_with_geojson_file,
            available_files=available_files_missing_prj,
        )


def test_get_additional_files_rapid_questionnaire_with_assets(
    questionnaire_file_with_assets_fixture, tapis_utils_with_geojson_file
):
    files = get_additional_files(
        questionnaire_file_with_assets_fixture,
        "testSystem",
        questionnaire_file_with_assets_fixture.filename,
        tapis_utils_with_geojson_file,
    )
    assert len(files) == 1


def test_get_additional_files_rapid_questionnaire_no_assets(
    questionnaire_file_without_assets_fixture, tapis_utils_with_geojson_file
):
    files = get_additional_files(
        questionnaire_file_without_assets_fixture,
        "testSystem",
        questionnaire_file_without_assets_fixture.filename,
        tapis_utils_with_geojson_file,
    )
    assert files == []
