import datetime
import uuid
from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models.project import Project


def test_get_projects(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/', headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1


def test_get_projects_not_allowed(test_client):
    resp = test_client.get('/projects/')
    assert resp.status_code == 403


def test_get_projects_using_uuids(test_client, projects_fixture, projects_fixture2):
    requested_uuids = [str(projects_fixture2.uuid), str(projects_fixture.uuid)]
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(','.join(requested_uuids)),
                           headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 2
    assert data[0]["uuid"] == requested_uuids[0]
    assert data[1]["uuid"] == requested_uuids[1]


def test_get_projects_using_single_uuid(test_client, projects_fixture, projects_fixture2):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(projects_fixture2.uuid),
                           headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["uuid"] == str(projects_fixture2.uuid)


def test_get_projects_using_single_uuid_that_is_wrong(test_client):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(uuid.uuid4()),
                           headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 404


def test_get_public_project_using_single_uuid(test_client, public_projects_fixture):
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(public_projects_fixture.uuid))
    assert resp.status_code == 200


def test_get_project_using_single_uuid_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(projects_fixture.uuid))
    assert resp.status_code == 403


def test_get_project_using_single_uuid_not_member_of_project(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(projects_fixture.uuid),
                           headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403


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


def test_project_data_protected(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.get('/projects/{}/'.format(projects_fixture.id), headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403


def test_project_data_allow_public_access(test_client, public_projects_fixture):
    resp = test_client.get('/projects/{}/'.format(public_projects_fixture.id))
    assert resp.status_code == 200

    u2 = db_session.query(User).get(2)
    resp = test_client.get('/projects/{}/'.format(public_projects_fixture.id), headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 200


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


def test_delete_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.delete('/projects/1/')
    assert resp.status_code == 403
    proj = db_session.query(Project).get(1)
    assert proj is not None


def test_add_user(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/1/users/',
        json={"username": "newUser"},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_add_user_unauthorized(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.post(
        '/projects/1/users/',
        json={"username": "newUser"},
        headers={'x-jwt-assertion-test': u2.jwt}
    )
    assert resp.status_code == 403


def test_add_user_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.post(
        '/projects/1/users/',
        json={"username": "newUser"},
    )
    assert resp.status_code == 403


def test_delete_user(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/1/users/',
        json={"username": "newUser"},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200
    resp = test_client.delete('/projects/1/users/newUser/',
                              headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200


def test_delete_user_unauthorized(test_client, projects_fixture):
    u2 = db_session.query(User).get(2)
    resp = test_client.delete('/projects/1/users/test1/',
                              headers={'x-jwt-assertion-test': u2.jwt})
    assert resp.status_code == 403

    test_client.delete('/projects/1/users/test1/')
    assert resp.status_code == 403


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


def test_get_point_clouds_listing(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/point-cloud/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1


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


def test_get_project_features_empty_public_access(test_client, public_projects_fixture):
    resp = test_client.get('/projects/{}/features/'.format(public_projects_fixture.id))
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


def test_get_project_features_single_feature_public_access(test_client, public_projects_fixture, feature_fixture):
    resp = test_client.get('/projects/{}/features/'.format(public_projects_fixture.id))
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


def test_import_shapefile_tapis(test_client, projects_fixture, import_file_from_agave_mock):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/1/features/files/import/',
        json={"files": [{"system": "designsafe.storage.default", "path": "file.shp"}]},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_observable_project(test_client,
                            userdata,
                            get_system_users_mock,
                            agave_utils_with_geojson_file_mock,
                            projects_fixture,
                            import_from_agave_mock):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/rapid/',
        json={"system_id": 'my_system', "path": '/some_path', "watch_content": True},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_observable_project_already_exists(test_client,
                                           observable_projects_fixture,
                                           agave_utils_with_geojson_file_mock,
                                           get_system_users_mock):
    u1 = db_session.query(User).get(1)
    data = {
        "system_id": observable_projects_fixture.system_id,
        "path": observable_projects_fixture.path,
        "watch_content": observable_projects_fixture.watch_content
    }
    resp = test_client.post(
        '/projects/rapid/',
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 409
    assert "Conflict, a project for this storage system/path already exists" in resp.json['message']


def test_update_project(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {'name': "Renamed Project", 'description': "New Description", 'public': True}
    resp = test_client.put(
        '/projects/1/',
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200
    proj = db_session.query(Project).get(1)
    assert proj.name == "Renamed Project"
    assert proj.description == "New Description"
    assert proj.public


def test_update_project_unauthorized_guest(test_client, public_projects_fixture):
    data = {'name': "Renamed Project", 'description': "New Description"}
    resp = test_client.put(
        '/projects/1/',
        json=data
    )
    assert resp.status_code == 403


def test_export_project(test_client,
                        projects_fixture,
                        get_system_users_mock,
                        agave_utils_with_geojson_file_mock):
    u1 = db_session.query(User).get(1)
    resp = test_client.put(
        '/projects/1/export/',
        json={"system_id": "testSystem",
              "path": "testPath",
              "file_name": "testFilename",
              "link": False},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200
