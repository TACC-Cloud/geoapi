from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models import Overlay

from unittest.mock import patch


def _get_overlay_data(extra):
    data = {"label": "test overlay",
            "minLat": 10, "maxLat": 20, "minLon": 15, "maxLon": 25}
    data.update(extra)
    return data


def test_get_overlay_permissions(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get('/projects/1/overlays/', headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403

    resp = test_client.get('/projects/1/overlays/')
    assert resp.status_code == 403


def test_get_overlay_public_access(test_client, public_projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get('/projects/1/overlays/', headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 200

    resp = test_client.get('/projects/1/overlays/')
    assert resp.status_code == 200


def test_post_overlay(test_client, projects_fixture, image_file_fixture):
    u1 = db_session.query(User).get(1)

    resp = test_client.post('/projects/1/overlays/',
                            data=_get_overlay_data({"file": image_file_fixture}),
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["minLat"] == 10
    assert data["maxLon"] == 25
    assert data["path"] is not None


@patch("geoapi.services.features.AgaveUtils")
def test_post_overlay_import_tapis(MockAgaveUtils, test_client, projects_fixture, image_file_fixture):
    MockAgaveUtils().getFile.return_value = image_file_fixture
    u1 = db_session.query(User).get(1)
    resp = test_client.post('/projects/1/overlays/import/',
                            json=_get_overlay_data({'system_id': "system", "path": "some_path"}),
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["minLat"] == 10
    assert data["maxLon"] == 25
    assert data["path"] is not None


def test_delete_overlay(test_client, projects_fixture, image_file_fixture):
    u1 = db_session.query(User).get(1)
    test_client.post('/projects/1/overlays/',
                     data=_get_overlay_data({"file": image_file_fixture}),
                     headers={'x-jwt-assertion-test': u1.jwt})

    u1 = db_session.query(User).get(1)
    resp = test_client.delete('/projects/1/overlays/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    proj = db_session.query(Overlay).get(1)
    assert proj is None
