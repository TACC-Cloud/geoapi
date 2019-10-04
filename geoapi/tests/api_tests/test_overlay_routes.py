from geoapi.models.users import User
from geoapi.models import Overlay


def _get_overlay_data(image_file):
    data = {"label": "test overlay",
            "minLat": 10, "maxLat": 20, "minLon": 15, "maxLon": 25,
            "file": image_file}
    return data


def test_post_overlay(test_client, dbsession, projects_fixture, image_file_fixture):
    u1 = dbsession.query(User).get(1)

    resp = test_client.post('/projects/1/overlays/',
                            data=_get_overlay_data(image_file_fixture),
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["minLat"] == 10
    assert data["maxLon"] == 25
    assert data["path"] is not None


def test_delete_overlay(test_client, dbsession, projects_fixture, image_file_fixture):
    u1 = dbsession.query(User).get(1)
    test_client.post('/projects/1/overlays/',
                     data=_get_overlay_data(image_file_fixture),
                     headers={'x-jwt-assertion-test': u1.jwt})

    u1 = dbsession.query(User).get(1)
    resp = test_client.delete('/projects/1/overlays/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    proj = dbsession.query(Overlay).get(1)
    assert proj is None
