from typing import TYPE_CHECKING
from geoapi.models.users import User
from geoapi.models import Overlay

from unittest.mock import patch


if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient


def _get_overlay_data(extra):
    data = {
        "label": "test overlay",
        "minLat": 10,
        "maxLat": 20,
        "minLon": 15,
        "maxLon": 25,
    }
    data.update(extra)
    return data


def test_get_overlay_permissions(test_client, projects_fixture, db_session):
    u2 = db_session.get(User, 2)
    resp = test_client.get("/projects/1/overlays/", headers={"X-Tapis-Token": u2.jwt})
    assert resp.status_code == 403

    resp = test_client.get("/projects/1/overlays/")
    assert resp.status_code == 403


def test_get_overlay_public_access(test_client, public_projects_fixture, db_session):
    u2 = db_session.get(User, 2)
    resp = test_client.get("/projects/1/overlays/", headers={"X-Tapis-Token": u2.jwt})
    assert resp.status_code == 200

    resp = test_client.get("/projects/1/overlays/")
    assert resp.status_code == 200


def test_post_overlay(test_client, projects_fixture, image_file_fixture, db_session):
    u1 = db_session.get(User, 1)

    resp = test_client.post(
        "/projects/1/overlays/",
        data=_get_overlay_data({}),
        files={"file": image_file_fixture},
        headers={"X-Tapis-Token": u1.jwt},
    )
    data = resp.json()
    assert resp.status_code == 201
    assert data["minLat"] == 10
    assert data["maxLon"] == 25
    assert data["path"] is not None


@patch("geoapi.services.features.TapisUtils")
def test_post_overlay_import_tapis(
    MockTapisUtils,
    test_client: "TestClient[Litestar]",
    projects_fixture,
    image_file_fixture,
    db_session,
):
    MockTapisUtils().getFile.return_value = image_file_fixture
    u1 = db_session.get(User, 1)
    resp = test_client.post(
        "/projects/1/overlays/import/",
        json=_get_overlay_data({"system_id": "system", "path": "some_path"}),
        headers={"X-Tapis-Token": u1.jwt},
    )
    data = resp.json()
    assert resp.status_code == 201
    assert data["minLat"] == 10
    assert data["maxLon"] == 25
    assert data["path"] is not None


def test_delete_overlay(
    test_client: "TestClient[Litestar]",
    projects_fixture,
    image_file_fixture,
    db_session,
):
    u1 = db_session.get(User, 1)
    test_client.post(
        "/projects/1/overlays/",
        data=_get_overlay_data({}),
        files={"file": image_file_fixture},
        headers={"X-Tapis-Token": u1.jwt},
    )

    u1 = db_session.get(User, 1)
    resp = test_client.delete(
        "/projects/1/overlays/1/", headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 204
    proj = db_session.get(Overlay, 1)
    assert proj is None
