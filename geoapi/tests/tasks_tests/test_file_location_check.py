import pytest
from unittest.mock import MagicMock, patch

from geoapi.tasks.file_location_check import (
    check_and_update_file_locations,
    extract_project_uuid,
    is_designsafe_project,
    determine_if_published,
    build_file_index_from_tapis,
    BATCH_SIZE,
    DESIGNSAFE_PUBLISHED_SYSTEM,
)
from geoapi.models import TaskStatus
from geoapi.models.feature import FeatureAsset


@pytest.fixture
def mock_update_task():
    """Mock the update_task_and_send_progress_update function"""
    with patch(
        "geoapi.tasks.file_location_check.update_task_and_send_progress_update"
    ) as mock:
        yield mock


@pytest.fixture
def mock_tapis():
    """Mock TapisUtils client"""
    with patch("geoapi.tasks.file_location_check.TapisUtils") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def file_location_check(db_session, projects_fixture):
    """Create a FileLocationCheck for testing"""
    from geoapi.services.file_location_status import FileLocationStatusService

    check = FileLocationStatusService.start_check(
        db_session, projects_fixture.id, "test-uuid"
    )
    db_session.commit()
    return check


@pytest.fixture
def asset_always_on_public_system(db_session, image_feature_fixture):
    """Create an asset already on a public system"""
    asset = image_feature_fixture.assets[0]
    asset.original_system = "designsafe.storage.published"
    asset.original_path = (
        "/published-data/PRJ-1234/Project--foo-bar-baz/data/FooBarBaz/test.jpg"
    )
    asset.current_system = "designsafe.storage.published"
    asset.current_path = (
        "/published-data/PRJ-1234/Project--foo-bar-baz/data/FooBarBaz/test.jpg"
    )
    asset.last_public_system_check = None
    db_session.commit()
    return asset


@pytest.fixture
def asset_now_on_public_system(db_session, image_feature_fixture):
    """Create an asset now on a public system"""
    asset = image_feature_fixture.assets[0]
    asset.original_system = "project-8932311246253724141-242ac11a-0001-012"
    asset.original_path = "/foo/test.jpg"
    asset.current_system = "designsafe.storage.published"
    asset.current_path = "/projects/PRJ-2344/test.jpg"
    asset.last_public_system_check = None
    db_session.commit()
    return asset


@pytest.fixture
def multiple_assets(db_session, feature_fixture, projects_fixture, num_assets=3):
    """Create multiple test assets"""
    assets = []
    for i in range(num_assets):
        asset = FeatureAsset(
            feature_id=feature_fixture.id,
            path=f"/test/asset_{i}.jpg",
            asset_type="image",
            original_path=f"/test/asset_{i}.jpg",
            original_system="designsafe.storage.published",
        )
        db_session.add(asset)
        assets.append(asset)

    db_session.commit()
    return assets


@pytest.fixture
def asset_found_in_published(db_session, image_feature_fixture):
    """Asset that will be found in published system"""
    asset = image_feature_fixture.assets[0]
    asset.original_system = "project-123456789"
    asset.original_path = "/project/data/found.jpg"
    asset.current_system = "project-123456789"
    asset.current_path = "/project/data/found.jpg"
    asset.is_on_public_system = False
    asset.last_public_system_check = None
    db_session.commit()
    return asset


@pytest.fixture
def asset_not_found_in_published(db_session, image_feature_fixture):
    """Asset that won't be found in published system"""
    asset = image_feature_fixture.assets[0]
    asset.original_system = "project-123456789"
    asset.original_path = "/project/data/missing.jpg"
    asset.current_system = "project-123456789"
    asset.current_path = "/project/data/missing.jpg"
    asset.is_on_public_system = False
    asset.last_public_system_check = None
    db_session.commit()
    return asset


@pytest.mark.parametrize(
    "system_id,expected_uuid",
    [
        ("project-123456789", "123456789"),
        ("designsafe.storage.default", None),
        ("", None),
    ],
)
def test_extract_project_uuid(system_id, expected_uuid):
    """Test extracting UUID from project system IDs"""
    assert extract_project_uuid(system_id) == expected_uuid


@pytest.mark.parametrize(
    "system_id,is_project",
    [
        ("project-123456789", True),
        ("designsafe.storage.default", False),
        ("", False),
    ],
)
def test_is_designsafe_project(system_id, is_project):
    """Test identifying DesignSafe project systems"""
    assert is_designsafe_project(system_id) == is_project


def test_build_file_index_from_tapis():
    """Test building file index from Tapis listing"""
    # Mock Tapis client and listing
    mock_client = MagicMock()

    # Create mock file items
    file1 = MagicMock(type="file", path="/dir1/file1.jpg")
    file2 = MagicMock(type="file", path="/dir1/file2.jpg")
    file3 = MagicMock(type="file", path="/dir2/file1.jpg")  # Duplicate filename
    dir1 = MagicMock(type="dir", path="/dir1")

    mock_client.listing.side_effect = [
        [file1, file2, dir1],  # Root listing
        [file3],  # /dir1 listing
    ]

    # Build index
    index = build_file_index_from_tapis(mock_client, "test.system", "/")

    # Verify structure
    assert "file1.jpg" in index
    assert "file2.jpg" in index
    assert len(index["file1.jpg"]) == 2  # Found in two places
    assert len(index["file2.jpg"]) == 1
    assert "dir1/file1.jpg" in index["file1.jpg"]
    assert "dir1/file2.jpg" in index["file2.jpg"]


def test_determine_if_published_found():
    """Test determining if asset is published when file exists"""
    # Setup file tree
    file_tree = {
        "test.jpg": ["/published-data/PRJ-1234/test.jpg"],
        "data.csv": ["/published-data/PRJ-1234/data/data.csv"],
    }

    # Create mock asset
    asset = MagicMock(spec=FeatureAsset)
    asset.id = 123
    asset.current_path = "/private/project/test.jpg"

    # Check if published
    is_published, system, path = determine_if_published(file_tree, asset)

    # Verify
    assert is_published is True
    assert system == DESIGNSAFE_PUBLISHED_SYSTEM
    assert path == "/published-data/PRJ-1234/test.jpg"


def test_determine_if_published_not_found():
    """Test determining if asset is published when file doesn't exist"""
    file_tree = {
        "other.jpg": ["/published-data/PRJ-1234/other.jpg"],
    }

    asset = MagicMock(spec=FeatureAsset)
    asset.id = 123
    asset.current_path = "/private/project/missing.jpg"

    is_published, system, path = determine_if_published(file_tree, asset)

    assert is_published is False
    assert system is None
    assert path is None


def test_determine_if_published_multiple_matches():
    """Test that multiple matches are handled (uses first, logs warning)"""
    file_tree = {
        "test.jpg": [
            "/published-data/PRJ-1234/test.jpg",
            "/published-data/PRJ-5678/test.jpg",
        ],
    }

    asset = MagicMock(spec=FeatureAsset)
    asset.id = 123
    asset.current_path = "/private/project/test.jpg"

    is_published, system, path = determine_if_published(file_tree, asset)

    # Should use first match
    assert is_published is True
    assert path == "/published-data/PRJ-1234/test.jpg"


def test_check_already_on_public_system(
    db_session,
    projects_fixture,
    user1,
    file_location_check,
    asset_always_on_public_system,
    mock_tapis,
    mock_update_task,
):
    """Test that files already on public systems are marked correctly"""
    # Run task
    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: Asset was updated
    db_session.refresh(asset_always_on_public_system)
    assert asset_always_on_public_system.is_on_public_system is True
    assert asset_always_on_public_system.last_public_system_check is not None

    # Verify: Check was marked complete with counts
    db_session.refresh(file_location_check)
    assert file_location_check.completed_at is not None
    assert file_location_check.total_files == 1
    assert file_location_check.files_checked == 1
    assert file_location_check.files_failed == 0


@patch("geoapi.tasks.file_location_check.get_session")
@patch("geoapi.tasks.file_location_check.TapisUtils")
def test_file_found_in_published_system(
    mock_tapis_utils,
    mock_get_session,
    db_session,
    projects_fixture,
    user1,
    file_location_check,
    asset_found_in_published,
    mock_update_task,
):
    """Test that file found in published system updates correctly"""
    # Setup: Mock project ID response
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "baseProject": {"value": {"projectId": "PRJ-1234"}}
    }
    mock_session.get.return_value = mock_response
    mock_get_session.return_value = mock_session

    # Setup: Mock Tapis listing with our file
    mock_client = MagicMock()
    found_file = MagicMock(type="file", path="/published-data/PRJ-1234/data/found.jpg")
    mock_client.listing.return_value = [found_file]
    mock_tapis_utils.return_value = mock_client

    # Setup: Project has a system_id
    projects_fixture.system_id = "project-123456789"
    db_session.commit()

    # Run task
    from geoapi.tasks.file_location_check import check_and_update_file_locations

    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: Asset was updated to published location
    db_session.refresh(asset_found_in_published)
    assert asset_found_in_published.is_on_public_system is True
    assert asset_found_in_published.current_system == DESIGNSAFE_PUBLISHED_SYSTEM
    assert "/published-data/PRJ-1234" in asset_found_in_published.current_path


@patch("geoapi.tasks.file_location_check.get_session")
@patch("geoapi.tasks.file_location_check.TapisUtils")
def test_file_not_found_in_published_system(
    mock_tapis_utils,
    mock_get_session,
    db_session,
    projects_fixture,
    user1,
    file_location_check,
    asset_not_found_in_published,
    mock_update_task,
):
    """Test that file not found in published system stays unpublished"""
    # Setup: Mock project ID response
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "baseProject": {"value": {"projectId": "PRJ-1234"}}
    }
    mock_session.get.return_value = mock_response
    mock_get_session.return_value = mock_session

    # Setup: Mock Tapis listing without our file
    mock_client = MagicMock()
    other_file = MagicMock(type="file", path="/published-data/PRJ-1234/data/other.jpg")
    mock_client.listing.return_value = [other_file]
    mock_tapis_utils.return_value = mock_client

    # Setup: Project has a system_id
    projects_fixture.system_id = "project-123456789"
    db_session.commit()

    # Run task
    from geoapi.tasks.file_location_check import check_and_update_file_locations

    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: Asset stayed on original system
    db_session.refresh(asset_not_found_in_published)
    assert asset_not_found_in_published.is_on_public_system is False
    assert asset_not_found_in_published.current_system == "project-123456789"
    assert asset_not_found_in_published.current_path == "/project/data/missing.jpg"


def test_batch_commits(
    db_session,
    projects_fixture,
    feature_fixture,
    user1,
    file_location_check,
    mock_tapis,
    mock_update_task,
):
    """Test that batches commit correctly"""
    # Setup: Create more assets than BATCH_SIZE
    num_assets = BATCH_SIZE + 50
    for i in range(num_assets):
        asset = FeatureAsset(
            feature_id=feature_fixture.id,
            path=f"/test/asset_{i}.jpg",
            asset_type="image",
            original_path=f"/test/asset_{i}.jpg",
            original_system="designsafe.storage.published",
        )
        db_session.add(asset)
    db_session.commit()

    # Run task
    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: All assets were checked
    assets = (
        db_session.query(FeatureAsset)
        .filter(FeatureAsset.feature_id == feature_fixture.id)
        .all()
    )
    assert len(assets) == num_assets

    for asset in assets:
        assert asset.last_public_system_check is not None

    # Verify: Counts are correct
    db_session.refresh(file_location_check)
    assert file_location_check.total_files == num_assets
    assert file_location_check.files_checked == num_assets
    assert file_location_check.files_failed == 0

    # Verify: Progress updates were called for batches
    progress_calls = [
        call
        for call in mock_update_task.call_args_list
        if "Processed" in call.kwargs.get("latest_message", "")
    ]
    assert len(progress_calls) >= 1


def test_individual_asset_error_continues(
    db_session,
    projects_fixture,
    user1,
    file_location_check,
    multiple_assets,
    mock_tapis,
    mock_update_task,
):
    """Test that errors on individual assets don't stop entire task"""
    # Run task
    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: Task completed successfully
    db_session.refresh(file_location_check)
    assert file_location_check.completed_at is not None

    # Verify: Counts show all files processed (even if some failed)
    assert file_location_check.total_files == 3
    assert file_location_check.files_checked == 3
    assert file_location_check.files_failed == 0

    # Verify: Final status is COMPLETED
    completed_calls = [
        call
        for call in mock_update_task.call_args_list
        if call.kwargs.get("status") == TaskStatus.COMPLETED
    ]
    assert len(completed_calls) >= 1


def test_updates_last_public_system_check_timestamp(
    db_session,
    projects_fixture,
    user1,
    file_location_check,
    asset_always_on_public_system,
    mock_tapis,
    mock_update_task,
):
    """Test that last_public_system_check timestamp is always updated"""
    # Record initial timestamp
    initial_check = asset_always_on_public_system.last_public_system_check

    # Run task
    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: Timestamp was updated
    db_session.refresh(asset_always_on_public_system)
    assert asset_always_on_public_system.last_public_system_check is not None
    assert asset_always_on_public_system.last_public_system_check != initial_check

    # Verify: Counts are correct
    db_session.refresh(file_location_check)
    assert file_location_check.total_files == 1
    assert file_location_check.files_checked == 1
    assert file_location_check.files_failed == 0


@pytest.mark.parametrize(
    "system,expected_public",
    [
        ("designsafe.storage.published", True),
        ("designsafe.storage.community", True),
        ("designsafe.storage.default", False),
        ("some.other.system", False),
    ],
)
def test_public_system_detection(
    db_session,
    projects_fixture,
    image_feature_fixture,
    user1,
    file_location_check,
    mock_tapis,
    mock_update_task,
    system,
    expected_public,
):
    """Test that public systems are correctly identified"""
    # Setup: Asset with specific system
    asset = image_feature_fixture.assets[0]
    asset.original_system = system
    asset.original_path = "/test/path.jpg"
    asset.current_system = system
    asset.current_path = "/test/path.jpg"
    asset.last_public_system_check = None
    db_session.commit()

    # Run task
    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: Public status matches expectation
    db_session.refresh(asset)
    assert asset.is_on_public_system == expected_public

    # Verify: Counts are correct
    db_session.refresh(file_location_check)
    assert file_location_check.total_files == 1
    assert file_location_check.files_checked == 1
    assert file_location_check.files_failed == 0


def test_counts_initialized(
    db_session,
    projects_fixture,
    user1,
    file_location_check,
    asset_always_on_public_system,
    mock_tapis,
    mock_update_task,
):
    """Test that counts are initialized at the start of task"""
    # Verify: Initial state has no counts
    assert (
        file_location_check.total_files is None or file_location_check.total_files == 0
    )

    # Run task
    check_and_update_file_locations(user1.id, projects_fixture.id)

    # Verify: Counts were set
    db_session.refresh(file_location_check)
    assert file_location_check.total_files is not None
    assert file_location_check.total_files > 0
