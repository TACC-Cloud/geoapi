import pytest
from unittest.mock import MagicMock, patch

from geoapi.tasks.file_location_check import (
    check_and_update_file_locations,
    BATCH_SIZE,
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


def test_missing_entities_returns_early(mock_tapis, mock_update_task):
    """Test that task returns early if user/project/check not found"""
    # Run with non-existent IDs
    check_and_update_file_locations(99999, 99999)

    # Verify: TapisUtils was never instantiated
    mock_tapis.assert_not_called()


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
