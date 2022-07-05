def test_get_project_using_single_uuid_unauthorized_guest(test_client, projects_fixture):
    resp = test_client.get('/public-projects/',
                           query_string='uuid={}'.format(projects_fixture.uuid))
    assert resp.status_code == 403


def test_get_public_project_using_single_uuid(test_client, public_projects_fixture):
    resp = test_client.get('/public-projects/',
                           query_string='uuid={}'.format(public_projects_fixture.uuid))
    assert resp.status_code == 200


def test_project_data_allow_public_access(test_client, public_projects_fixture):
    resp = test_client.get('/public-projects/{}/'.format(public_projects_fixture.id))
    assert resp.status_code == 200


def test_put_project_not_found(test_client, projects_fixture):
    data = {'name': "Renamed Project", 'description': "New Description", 'public': True}
    resp = test_client.put(
        '/public-projects/{}/'.format(projects_fixture),
        json=data
    )
    assert resp.status_code == 404


def test_delete_project_not_found(test_client, projects_fixture):
    resp = test_client.delete('/public-projects/21/')
    assert resp.status_code == 405


def test_get_project_features_empty_public_access(test_client, public_projects_fixture):
    resp = test_client.get('/public-projects/{}/features/'.format(public_projects_fixture.id))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['features']) == 0


def test_get_project_features_single_feature_public_access(test_client, public_projects_fixture, feature_fixture):
    resp = test_client.get('/public-projects/{}/features/'.format(public_projects_fixture.id))
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['features']) != 0


def test_get_overlay_public_access(test_client, public_projects_fixture):
    resp = test_client.get('/public-projects/1/overlays/')
    assert resp.status_code == 200


def test_get_point_clouds_listing(test_client, public_projects_fixture, point_cloud_fixture):
    resp = test_client.get('/projects/1/point-cloud/')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1


def test_get_point_cloud_public_access(test_client, public_projects_fixture, point_cloud_fixture):
    resp = test_client.get('/public-projects/1/point-cloud/1/')
    assert resp.status_code == 200


def test_post_feature_import_not_found(test_client, projects_fixture, import_file_from_agave_mock):
    resp = test_client.post(
        '/public-projects/1/features/files/import/',
        json={"files": [{"system": "designsafe.storage.default", "path": "file.jpg"}]}
    )
    assert resp.status_code == 404


def test_post_feature_not_found(test_client, projects_fixture, image_file_fixture):
    resp = test_client.post(
        '/public-projects/1/features/files/',
        data={"file": image_file_fixture}
    )
    assert resp.status_code == 404

# TODO test tile server
