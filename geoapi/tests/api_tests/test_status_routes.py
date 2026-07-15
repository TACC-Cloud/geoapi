from unittest.mock import patch, MagicMock
from celery.exceptions import TimeoutError as CeleryTimeoutError


def test_get_status_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.get("/status/")
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"status": "OK"}


def test_get_status(test_client, user1):
    resp = test_client.get("/status/", headers={"X-Tapis-Token": user1.jwt})
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"status": "OK"}


def test_get_status_complete_unauthorized(test_client):
    resp = test_client.get("/status/complete")
    assert resp.status_code == 401


def test_get_status_complete_ok(test_client, user1):
    mock_result = {
        "overall": "ok",
        "components": {
            "redis": {"status": "ok", "detail": None},
            "database": {"status": "ok", "detail": None},
        },
    }
    with patch("geoapi.routes.status.check_worker") as mock_task, patch(
        "geoapi.routes.status.AsyncResult"
    ) as mock_async_result:
        mock_task.delay.return_value = MagicMock(id="fake-id")
        mock_async_result.return_value.get.return_value = mock_result

        resp = test_client.get("/status/complete", headers={"X-Tapis-Token": user1.jwt})
    assert resp.status_code == 200
    assert resp.json()["overall"] == "ok"


def test_get_status_complete_error(test_client, user1):
    mock_result = {
        "overall": "error",
        "components": {
            "redis": {"status": "error", "detail": "Timeout connecting to server"},
            "database": {"status": "ok", "detail": None},
        },
    }
    with patch("geoapi.routes.status.check_worker") as mock_task, patch(
        "geoapi.routes.status.AsyncResult"
    ) as mock_async_result:
        mock_task.delay.return_value = MagicMock(id="fake-id")
        mock_async_result.return_value.get.return_value = mock_result

        resp = test_client.get("/status/complete", headers={"X-Tapis-Token": user1.jwt})
    assert resp.status_code == 503
    assert resp.json()["overall"] == "error"


def test_get_status_complete_worker_timeout(test_client, user1):
    with patch("geoapi.routes.status.check_worker") as mock_task, patch(
        "geoapi.routes.status.AsyncResult"
    ) as mock_async_result:
        mock_task.delay.return_value = MagicMock(id="fake-id")
        mock_async_result.return_value.get.side_effect = CeleryTimeoutError()

        resp = test_client.get("/status/complete", headers={"X-Tapis-Token": user1.jwt})
    assert resp.status_code == 503
