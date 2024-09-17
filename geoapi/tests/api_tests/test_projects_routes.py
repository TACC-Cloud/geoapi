import datetime
import uuid
import os
from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models.project import Project, ProjectUser
from geoapi.utils.assets import get_project_asset_dir


def test_get_projects(test_client, projects_fixture, user1):
    resp = test_client.get('/projects/', headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["deletable"] is True


def test_get_projects_but_not_admin_or_creator(test_client, user2, projects_fixture2, projects_fixture):
    resp = test_client.get('/projects/', headers={'X-Tapis-Token': user2.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["id"] == projects_fixture2.id
    assert data[0]["deletable"] is False


def test_get_projects_with_multiple(test_client, user1, projects_fixture2, projects_fixture):
    resp = test_client.get('/projects/', headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 2
    assert data[0]["deletable"] is True
    assert data[0]["id"] == projects_fixture.id
    assert data[1]["id"] == projects_fixture2.id
    assert data[1]["deletable"] is True


def test_get_projects_not_allowed(test_client):
    resp = test_client.get('/projects/')
    assert resp.status_code == 403


def test_get_projects_using_uuids(test_client, projects_fixture, projects_fixture2, user1):
    requested_uuids = [str(projects_fixture2.uuid), str(projects_fixture.uuid)]
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(','.join(requested_uuids)),
                           headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 2
    assert data[0]["uuid"] == requested_uuids[0]
    assert data[1]["uuid"] == requested_uuids[1]


def test_get_projects_using_single_uuid(test_client, projects_fixture, projects_fixture2, user1):
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(projects_fixture2.uuid),
                           headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["uuid"] == str(projects_fixture2.uuid)
    assert data[0]["deletable"] is True


def test_get_projects_using_single_uuid_that_is_wrong(test_client, user1):
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(uuid.uuid4()),
                           headers={'X-Tapis-Token': user1.jwt})
    assert resp.status_code == 404


def test_get_public_project_using_single_uuid(test_client, public_projects_fixture):
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(public_projects_fixture.uuid))
    assert resp.status_code == 200


def test_get_project_using_single_uuid_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(projects_fixture.uuid))
    assert resp.status_code == 403


def test_get_project_using_single_uuid_not_member_of_project(test_client, projects_fixture, user2):
    resp = test_client.get('/projects/',
                           query_string='uuid={}'.format(projects_fixture.uuid),
                           headers={'X-Tapis-Token': user2.jwt})
    assert resp.status_code == 403


def test_project_permissions(test_client, projects_fixture, user2):
    resp = test_client.get('/projects/', headers={'X-Tapis-Token': user2.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 0


def test_project_protected(test_client, projects_fixture, user2):
    resp = test_client.get(f'/projects/{projects_fixture.id}/', headers={'X-Tapis-Token': user2.jwt})
    assert resp.status_code == 403


def test_project_data(test_client, projects_fixture, user1):
    resp = test_client.get('/projects/', headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data[0]["name"] == projects_fixture.name
    assert data[0]["description"] == projects_fixture.description
    assert data[0]["deletable"] is True


def test_project_data_single(test_client, projects_fixture, user1):
    resp = test_client.get(f'/projects/{projects_fixture.id}/', headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["name"] == projects_fixture.name
    assert data["description"] == projects_fixture.description
    assert data["deletable"] is True


def test_project_data_protected(test_client, projects_fixture, user2):
    resp = test_client.get(f'/projects/{projects_fixture.id}/', headers={'X-Tapis-Token': user2.jwt})
    assert resp.status_code == 403


def test_project_data_allow_public_access(test_client, public_projects_fixture, user2):
    resp = test_client.get(f'/projects/{public_projects_fixture.id}/')
    assert resp.status_code == 200

    resp = test_client.get(f'/projects/{public_projects_fixture.id}/', headers={'X-Tapis-Token': user2.jwt})
    assert resp.status_code == 200


def test_delete_empty_project(test_client, projects_fixture, remove_project_assets_mock, user1):
    resp = test_client.delete(f'/projects/{projects_fixture.id}/', headers={'X-Tapis-Token': user1.jwt})
    assert resp.status_code == 200
    projects = db_session.query(Project).all()
    projectUsers = db_session.query(ProjectUser).all()
    assert projects == []
    assert projectUsers == []


def test_delete_project(test_client, projects_fixture, remove_project_assets_mock, image_feature_fixture, user1):
    assert os.path.isdir(get_project_asset_dir(projects_fixture.id))
    resp = test_client.delete(f'/projects/{projects_fixture.id}/', headers={'X-Tapis-Token': user1.jwt})
    assert resp.status_code == 200
    projects = db_session.query(Project).all()
    projectUsers = db_session.query(ProjectUser).all()
    assert projects == []
    assert projectUsers == []
    assert not os.path.isdir(get_project_asset_dir(projects_fixture.id))


def test_delete_unauthorized(test_client, projects_fixture, user2):
    resp = test_client.delete(f'/projects/{projects_fixture.id}/', headers={'X-Tapis-Token': user2.jwt})
    assert resp.status_code == 403
    proj = db_session.query(Project).get(1)
    assert proj is not None


def test_delete_project_not_admin_or_creator(test_client, projects_fixture2, projects_fixture, user2):
    resp = test_client.delete(f'/projects/{projects_fixture2.id}/', headers={'X-Tapis-Token': user2.jwt})
    assert resp.status_code == 403


def test_delete_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.delete(f'/projects/{projects_fixture.id}/')
    assert resp.status_code == 403
    proj = db_session.query(Project).get(1)
    assert proj is not None


def test_get_users(test_client, projects_fixture, user1):
    resp = test_client.get(
        f'/projects/{projects_fixture.id}/users/',
        headers={'X-Tapis-Token': user1.jwt}
    )
    assert resp.status_code == 200
    assert resp.get_json() == [{"id": user1.id, "username": user1.username}]


def test_add_user(test_client, projects_fixture, user1):
    resp = test_client.post(
        f'/projects/{projects_fixture.id}/users/',
        json={"username": "newUser", "admin": False},
        headers={'X-Tapis-Token': user1.jwt}
    )
    assert resp.status_code == 200


def test_add_user_unauthorized(test_client, projects_fixture, user2):
    resp = test_client.post(
        f'/projects/{projects_fixture.id}/users/',
        json={"username": "newUser"},
        headers={'X-Tapis-Token': user2.jwt}
    )
    assert resp.status_code == 403


def test_add_user_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.post(
        f'/projects/{projects_fixture.id}/users/',
        json={"username": "newUser"},
    )
    assert resp.status_code == 403


def test_delete_user(test_client, projects_fixture2, user1, user2):
    resp = test_client.delete(f'/projects/{projects_fixture2.id}/users/{user2.username}/',
                              headers={'X-Tapis-Token': user1.jwt})
    assert resp.status_code == 200


def test_delete_user_unauthorized(test_client, projects_fixture, user2):
    resp = test_client.delete(f'/projects/{projects_fixture.id}/users/test1/',
                              headers={'X-Tapis-Token': user2.jwt})
    assert resp.status_code == 403

    test_client.delete('/projects/1/users/test1/')
    assert resp.status_code == 403


def test_upload_gpx(test_client, projects_fixture, gpx_file_fixture, user1):
    resp = test_client.post(
        f'/projects/{projects_fixture.id}/features/files/',
        data={"file": gpx_file_fixture},
        headers={'X-Tapis-Token': user1.jwt}
    )
    assert resp.status_code == 200


def test_upload_image(test_client, projects_fixture, image_file_fixture, user1):
    resp = test_client.post(
        f'/projects/{projects_fixture.id}/features/files/',
        data={"file": image_file_fixture},
        headers={'X-Tapis-Token': user1.jwt}
    )
    assert resp.status_code == 200


def test_import_image_tapis(test_client, projects_fixture, import_file_from_agave_mock, user1):
    resp = test_client.post(
        f'/projects/{projects_fixture.id}/features/files/import/',
        json={"files": [{"system": "designsafe.storage.default", "path": "file.jpg"}]},
        headers={'X-Tapis-Token': user1.jwt}
    )
    assert resp.status_code == 200


def test_get_point_clouds_listing(test_client, projects_fixture, point_cloud_fixture, user1):
    resp = test_client.get(f'/projects/{projects_fixture.id}/point-cloud/',
                           headers={'X-Tapis-Token': user1.jwt})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1


def test_get_point_cloud(test_client, projects_fixture, point_cloud_fixture, user1):
    resp = test_client.get(f'/projects/{projects_fixture.id}/point-cloud/1/',
                           headers={'X-Tapis-Token': user1.jwt})
    assert resp.status_code == 200


def test_get_project_features_empty(test_client, projects_fixture, user1, caplog):
    resp = test_client.get(f'/projects/{projects_fixture.id}/features/',
                           headers={'X-Tapis-Token': user1.jwt})
    assert resp.status_code == 200

    data = resp.get_json()
    assert len(data['features']) == 0
    log_statement_for_analytics = (f"Get features of project for user:{user1.username} application:Unknown public_view:False "
                                   f"project_uuid:{projects_fixture.uuid} project:{projects_fixture.id} "
                                   f"tapis_system_id:None tapis_system_path:None")
    assert log_statement_for_analytics in caplog.text


def test_get_project_features_empty_public_access(test_client, public_projects_fixture, caplog):
    resp = test_client.get('/public-projects/{}/features/'.format(public_projects_fixture.id))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['features']) == 0
    log_statement_for_analytics = (f"Get features of project for user:Guest_Unknown application:Unknown public_view:True "
                                   f"project_uuid:{public_projects_fixture.uuid} project:{public_projects_fixture.id} "
                                   f"tapis_system_id:None tapis_system_path:None")
    assert log_statement_for_analytics in caplog.text


def test_get_project_features_analytics_with_query_params(test_client, public_projects_fixture, caplog):
    # send analytics-related params to projects endpoint only (until we use headers again
    # in https://tacc-main.atlassian.net/browse/WG-192)
    query = {'application': 'hazmapper', 'guest_uuid': "1234"}
    test_client.get('/public-projects/{}/features/'.format(public_projects_fixture.id), query_string=query)
    log_statement_for_analytics = (f"Get features of project for user:Guest_1234 application:hazmapper public_view:True "
                                   f"project_uuid:{public_projects_fixture.uuid} project:{public_projects_fixture.id} "
                                   f"tapis_system_id:None tapis_system_path:None")
    assert log_statement_for_analytics in caplog.text


def test_get_project_features_single_feature(test_client, projects_fixture, feature_fixture, user1):
    resp = test_client.get(f'/projects/{projects_fixture.id}/features/',
                           headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) != 0


def test_get_project_features_single_feature_public_access(test_client, public_projects_fixture, feature_fixture):
    resp = test_client.get('/projects/{}/features/'.format(public_projects_fixture.id))
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) != 0


def test_get_project_features_filter_with_assettype(test_client, projects_fixture,
                                                    feature_fixture, image_feature_fixture, user1):
    resp = test_client.get(f'/projects/{projects_fixture.id}/features/',
                           query_string={'assetType': 'image'},
                           headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) == 1


def test_get_project_features_filter_with_bounding_box(test_client, projects_fixture,
                                                       feature_fixture, image_feature_fixture):
    # feature fixture is (125.6, 10.1)
    # image is (-80.78037499999999, 32.61850555555556)
    bbox = [-80.9, 32.61, -80, 32.62]  # query just the image
    u1 = db_session.query(User).get(1)
    resp = test_client.get(f'/projects/{projects_fixture.id}/features/',
                           query_string='bbox={}'.format(','.join(map(str, bbox))),
                           headers={'X-Tapis-Token': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) == 1


def test_get_project_features_filter_with_date_range(test_client, projects_fixture, feature_fixture, user1):
    start_date = (datetime.datetime.now()-datetime.timedelta(minutes=5)).isoformat()
    end_date = (datetime.datetime.now()+datetime.timedelta(minutes=5)).isoformat()
    resp = test_client.get(f'/projects/{projects_fixture.id}/features/',
                           query_string={'startDate': start_date,
                                         'endDate': end_date},
                           headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert projects_fixture.id == feature_fixture.id
    assert len(data['features']) == 1

    start_date = (datetime.datetime.now()+datetime.timedelta(minutes=1)).isoformat()
    resp = test_client.get(f'/projects/{projects_fixture.id}/features/',
                           query_string={'startDate': start_date,
                                         'endDate': end_date},
                           headers={'X-Tapis-Token': user1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) == 0


def test_import_shapefile_tapis(test_client, projects_fixture, import_file_from_agave_mock, user1):
    resp = test_client.post(
        f'/projects/{projects_fixture.id}/features/files/import/',
        json={"files": [{"system": "designsafe.storage.default", "path": "file.shp"}]},
        headers={'X-Tapis-Token': user1.jwt}
    )
    assert resp.status_code == 200


def test_update_project(test_client, projects_fixture, user1):
    data = {
        'name': "Renamed Project",
        'description': "New Description",
        'public': True
    }
    resp = test_client.put(
        f'/projects/{projects_fixture.id}/',
        json=data,
        headers={'X-Tapis-Token': user1.jwt}
    )
    assert resp.status_code == 200
    proj = db_session.query(Project).get(1)
    assert proj.name == "Renamed Project"
    assert proj.description == "New Description"
    assert proj.public


def test_update_project_unauthorized_guest(test_client, public_projects_fixture):
    data = {
        'name': "Renamed Project",
        'description': "New Description",
        'public': True
    }
    resp = test_client.put(
        f'/projects/{public_projects_fixture.id}/',
        json=data
    )
    assert resp.status_code == 403


def test_create_project_watch_content_already_exists(test_client,
                                                     watch_content_users_projects_fixture,
                                                     get_system_users_mock,
                                                     import_from_agave_mock,
                                                     agave_utils_with_geojson_file_mock,
                                                     user1):
    data = {
        'name': 'Project name',
        'description': 'Project description',
        'system_id': watch_content_users_projects_fixture.system_id,
        'system_path': watch_content_users_projects_fixture.system_path,
        'system_file': 'testFilename',
        'watch_users': True,
        'watch_content': True
    }

    resp = test_client.post(
        '/projects/',
        json=data,
        headers={'X-Tapis-Token': user1.jwt}
    )

    assert resp.status_code == 409
    assert "Conflict, a project watching files for this storage system/path already exists" in resp.json['message']


def test_create_project_with_watch_content_watch_users(test_client,
                                                       get_system_users_mock,
                                                       import_from_agave_mock,
                                                       agave_utils_with_geojson_file_mock, user1):
    data = {
        'name': 'Project name',
        'description': 'Project description',
        'system_id': 'testSystem',
        'system_path': 'testPath',
        'system_file': 'testFilename',
        'watch_users': True,
        'watch_content': False
    }
    resp = test_client.post('/projects/',
                            json=data,
                            headers={'X-Tapis-Token': user1.jwt})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["deletable"] is True
    assert data["name"] == "Project name"

    proj = db_session.query(Project).get(1)
    assert proj.name == "Project name"


def test_create_project_unauthorized(test_client):
    data = {
        'name': 'Project name',
        'description': 'Project description',
        'system_id': 'testSystem',
        'system_path': 'testPath',
        'system_file': 'testFilename',
        'watch_users': True,
        'watch_content': False
    }

    resp = test_client.post('/projects/', json=data)

    assert resp.status_code == 403
