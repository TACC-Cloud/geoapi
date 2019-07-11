from geoapi.models.users import User
from geoapi.models.project import Project

def test_get_projects(test_client, projects_fixture):
    u1 = User.query.get(1)
    resp = test_client.get('/projects/', headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1

def test_project_permissions(test_client, projects_fixture):
    u2 = User.query.get(2)
    resp = test_client.get('/projects/', headers={'x-jwt-assertion-test': u2.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 0

def test_project_protected(test_client, projects_fixture):
    u2 = User.query.get(2)
    resp = test_client.get('/projects/1/', headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403

def test_project_data(test_client, projects_fixture):
    u1 = User.query.get(1)
    resp = test_client.get('/projects/', headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert data[0]["name"] == "test"
    assert data[0]["description"] == "test"

def test_delete_empty_project(test_client, projects_fixture):
    u1 = User.query.get(1)
    resp = test_client.delete('/projects/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    proj = Project.query.get(1)
    assert proj is None

def test_delete_unauthorized(test_client, projects_fixture):
    u2 = User.query.get(2)
    resp = test_client.delete('/projects/1/', headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403
    proj = Project.query.get(1)
    assert proj is not None

def test_upload_gpx(test_client, projects_fixture, gpx_file_fixture):
    u1 = User.query.get(1)
    resp = test_client.post(
        '/projects/1/features/files/',
        data={"file": gpx_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200

def test_upload_image(test_client, projects_fixture, image_file_fixture):
    u1 = User.query.get(1)
    resp = test_client.post(
        '/projects/1/features/files/',
        data={"file": image_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200

def test_upload_feature_properties(test_client, projects_fixture, feature_properties_file_fixture):
    u1 = User.query.get(1)
    resp = test_client.post(
        '/projects/1/features/files/',
        data={"file": feature_properties_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200
