from geoapi.models.users import User
from geoapi.models.project import Project

def test_post_overlay(test_client, dbsession, projects_fixture, image_file_fixture):
    u1 = dbsession.query(User).get(1)
    resp = test_client.post('/projects/1/overlays/',
                            data={
                                "file": image_file_fixture,
                                "label": "test overlay",
                                "minLat": 10,
                                "maxLat": 20,
                                "minLon": 15,
                                "maxLon": 25
                            },
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["minLat"] == 10
    assert data["maxLon"] == 25
    assert data["path"] is not None

