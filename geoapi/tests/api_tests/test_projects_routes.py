from geoapi.db import db_session

from geoapi.models.users import User
from geoapi.models.project import Project
import datetime


def test_get_projects(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/', headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1


def test_project_permissions(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get('/projects/', headers={'x-jwt-assertion-test': u2.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 0


def test_project_protected(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get('/projects/1/', headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403


def test_project_data(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/', headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert data[0]["name"] == "test"
    assert data[0]["description"] == "description"


def test_delete_empty_project(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete('/projects/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    proj = db_session.query(Project).get(1)
    assert proj is None


def test_delete_unauthorized(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.delete('/projects/1/', headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403
    proj = db_session.query(Project).get(1)
    assert proj is not None


def test_upload_gpx(test_client, projects_fixture, gpx_file_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/1/features/files/',
        data={"file": gpx_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_upload_image(test_client, projects_fixture, image_file_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/1/features/files/',
        data={"file": image_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_import_image_tapis(test_client, projects_fixture, import_file_from_agave_mock):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/1/features/files/import/',
        json={"files": [{"system": "designsafe.storage.default", "path": "file.jpg"}]},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_get_point_cloud(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/point-cloud/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200


def test_get_project_features_empty(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/features/',
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200

    data = resp.get_json()
    assert len(data['features']) == 0


def test_get_project_features_single_feature(test_client, projects_fixture, feature_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/features/',
                           headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) != 0


def test_get_project_features_filter_with_assettype(test_client, projects_fixture,
                                                    feature_fixture, image_feature_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/features/',
                           query_string={'assetType': 'image'},
                           headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) == 1


def test_get_project_features_filter_with_bounding_box(test_client, projects_fixture,
                                                       feature_fixture, image_feature_fixture):
    bbox = [-80.9, 32.61, -80, 32.62]
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/features/',
                           query_string='bbox={}'.format(','.join(map(str, bbox))),
                           headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) == 1


def test_get_project_features_filter_with_date_range(test_client, projects_fixture, feature_fixture):
    u1 = db_session.query(User).get(1)
    start_date = (datetime.datetime.now()-datetime.timedelta(minutes=5)).isoformat()
    end_date = (datetime.datetime.now()+datetime.timedelta(minutes=5)).isoformat()
    resp = test_client.get('/projects/1/features/',
                           query_string={'startDate': start_date,
                                         'endDate': end_date},
                           headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) == 1

    start_date = (datetime.datetime.now()+datetime.timedelta(minutes=1)).isoformat()
    resp = test_client.get('/projects/1/features/',
                           query_string={'startDate': start_date,
                                         'endDate': end_date},
                           headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) == 0
