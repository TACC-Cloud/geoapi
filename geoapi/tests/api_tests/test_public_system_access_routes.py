import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def check_public_paths_mock():
    with patch(
        "geoapi.routes.public_system_access.check_and_update_system_paths"  # Patch where it's used
    ) as mock_task:
        mock_task.apply_async.return_value = MagicMock(id="mock-task-id")
        yield mock_task


def test_start_public_status_refresh(
    test_client, projects_fixture, user1, check_public_paths_mock
):
    resp = test_client.post(
        f"/projects/{projects_fixture.id}/public-system-access/",
        headers={"X-Tapis-Token": user1.jwt},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["message"] == "Public status refresh started"
    assert data["public_status_id"] is not None
    assert data["task_id"] is not None

    # Verify the task was called
    check_public_paths_mock.apply_async.assert_called_once()


def test_start_public_status_refresh_already_running(
    test_client, projects_fixture, user1, check_public_paths_mock
):
    # Start first refresh
    test_client.post(
        f"/projects/{projects_fixture.id}/public-system-access/",
        headers={"X-Tapis-Token": user1.jwt},
    )

    # Try to start second refresh
    resp = test_client.post(
        f"/projects/{projects_fixture.id}/public-system-access/",
        headers={"X-Tapis-Token": user1.jwt},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "already in progress" in data["message"]


def test_start_public_status_refresh_unauthorized(
    test_client, projects_fixture, check_public_paths_mock
):
    resp = test_client.post(f"/projects/{projects_fixture.id}/public-system-access/")
    assert resp.status_code == 401
    check_public_paths_mock.apply_async.assert_not_called()


def test_start_public_status_refresh_forbidden(test_client, projects_fixture, user2):
    resp = test_client.post(
        f"/projects/{projects_fixture.id}/public-system-access/",
        headers={"X-Tapis-Token": user2.jwt},
    )
    assert resp.status_code == 403


def test_get_public_files_status_empty(test_client, projects_fixture, user1):
    resp = test_client.get(
        f"/projects/{projects_fixture.id}/public-system-access/files",
        headers={"X-Tapis-Token": user1.jwt},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == projects_fixture.id
    assert data["check"] is None
    assert data["files"] == []


def test_get_public_files_status_with_features(
    test_client, projects_fixture, image_feature_fixture, user1
):
    resp = test_client.get(
        f"/projects/{projects_fixture.id}/public-system-access/files",
        headers={"X-Tapis-Token": user1.jwt},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == projects_fixture.id
    assert len(data["files"]) == 1
    assert data["files"][0]["asset_type"] == "image"


def test_get_public_files_status_unauthorized(test_client, projects_fixture):
    resp = test_client.get(
        f"/projects/{projects_fixture.id}/public-system-access/files"
    )
    assert resp.status_code == 401


def test_get_public_files_status_forbidden(test_client, projects_fixture, user2):
    resp = test_client.get(
        f"/projects/{projects_fixture.id}/public-system-access/files",
        headers={"X-Tapis-Token": user2.jwt},
    )
    assert resp.status_code == 403
