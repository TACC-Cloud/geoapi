from geoapi.models.users import User
from geoapi.models import TileServer, Task
from unittest.mock import patch, MagicMock


def _get_tile_server_data():
    data = {
        "name": "Test",
        "type": "tms",
        "url": "www.test.com",
        "attribution": "contributors",
    }

    return data


# TODO add tile server listing and public listing test


def test_add_tile_server(test_client, projects_fixture, db_session):
    u1 = db_session.get(User, 1)

    resp = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )
    data = resp.json()
    assert resp.status_code == 201
    assert data["name"] == "Test"
    assert data["type"] == "tms"
    assert data["url"] == "www.test.com"
    assert data["attribution"] == "contributors"


def test_delete_tile_server(test_client, projects_fixture, db_session):
    u1 = db_session.get(User, 1)
    test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    resp = test_client.delete(
        "/projects/1/tile-servers/1/", headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 204
    proj = db_session.get(TileServer, 1)
    assert proj is None


def test_update_tile_server(test_client, projects_fixture, db_session):
    u1 = db_session.get(User, 1)

    resp = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    data = {
        "name": "NewTestName",
    }

    resp = test_client.put(
        "/projects/1/tile-servers/1/", json=data, headers={"X-Tapis-Token": u1.jwt}
    )

    assert resp.status_code == 200
    tsv = db_session.get(TileServer, 1)
    assert tsv.name == "NewTestName"


def test_update_tile_servers(test_client, projects_fixture, db_session):
    u1 = db_session.get(User, 1)

    resp1 = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    resp2 = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    updated_data = [
        {"id": resp1.json()["id"], "name": "NewTestName1"},
        {"id": resp2.json()["id"], "name": "NewTestName2"},
    ]

    resp = test_client.put(
        "/projects/1/tile-servers/",
        json=updated_data,
        headers={"X-Tapis-Token": u1.jwt},
    )

    assert resp.status_code == 200

    my_tsv1 = db_session.get(TileServer, 1)
    assert my_tsv1.name == "NewTestName1"

    my_tsv2 = db_session.get(TileServer, 2)
    assert my_tsv2.name == "NewTestName2"


def test_import_tile_server_ini_file_tapis(
    test_client, projects_fixture, import_file_from_tapis_mock, db_session
):

    u1 = db_session.get(User, 1)
    resp = test_client.post(
        "/projects/1/features/files/import/",
        json={
            "files": [{"system": "designsafe.storage.default", "path": "metadata.ini"}]
        },
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 201


def test_import_tile_server_files_route__tasks_queued(
    test_client, projects_fixture, db_session, user1
):
    """Test that tile server import route creates tasks and queues celery jobs"""

    files = ["/path/to/raster1.tif", "/path/to/raster2.tif"]
    # Mock the celery task's apply_async method
    with patch(
        "geoapi.tasks.raster.import_tile_servers_from_tapis.apply_async"
    ) as mock_apply_async:
        # Make it return a mock result (celery's AsyncResult)
        mock_apply_async.return_value = MagicMock()

        # Make the request with multiple files
        resp = test_client.post(
            "/projects/1/tile-servers/files/import/",
            json={
                "files": [
                    {"system": "designsafe.storage.default", "path": files[0]},
                    {"system": "designsafe.storage.default", "path": files[1]},
                ]
            },
            headers={"X-Tapis-Token": user1.jwt},
        )

    # Verify response (2 tasks for the 2 files)
    assert resp.status_code == 201
    tasks_data = resp.json()
    assert len(tasks_data) == 2

    for task_index, task_data in enumerate(tasks_data):
        # Verify each task in the response
        assert task_data["status"] == "QUEUED"
        assert "Add tile-server for" in task_data["description"]
        assert files[task_index] in task_data["description"]
        assert task_data["id"] is not None

        # Verify corresponding celery call (i.e. import_tile_servers_from_tapis)
        mocked_call = mock_apply_async.call_args_list[task_index]
        assert mocked_call.kwargs["kwargs"]["user_id"] == user1.id
        assert mocked_call.kwargs["kwargs"]["project_id"] == projects_fixture.id
        assert (
            mocked_call.kwargs["kwargs"]["tapis_file"]["system"]
            == "designsafe.storage.default"
        )
        assert mocked_call.kwargs["kwargs"]["tapis_file"]["path"] == files[task_index]
        assert "task_id" in mocked_call.kwargs["kwargs"]

        # Verify the task exists in database
        db_task = db_session.get(Task, task_data["id"])
        assert db_task is not None
        assert db_task.status == "QUEUED"
        assert mocked_call.kwargs["task_id"] == db_task.process_id

    # Verify celery tasks were dispatched
    assert mock_apply_async.call_count == 2


def test_import_tile_server_files_route__requires_auth(
    test_client, projects_fixture, db_session
):
    """Test that authentication is required"""
    resp = test_client.post(
        "/projects/1/tile-servers/files/import/",
        json={"files": [{"system": "test.system", "path": "/raster.tif"}]},
    )
    assert resp.status_code in [401, 403]


def test_import_tile_server_files_route__requires_project_permission(
    test_client, projects_fixture, db_session, user2
):
    """Test that user needs permission to the project"""
    # user2 is not part of projects_fixture (only user1 is)
    with patch("geoapi.tasks.raster.import_tile_servers_from_tapis.apply_async"):
        resp = test_client.post(
            "/projects/1/tile-servers/files/import/",
            json={"files": [{"system": "test.system", "path": "/raster.tif"}]},
            headers={"X-Tapis-Token": user2.jwt},
        )

    # Should fail - user2 doesn't have access
    assert resp.status_code in [401, 403]
