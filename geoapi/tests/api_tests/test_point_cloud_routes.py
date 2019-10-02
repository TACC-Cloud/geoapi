from geoapi.models import User, PointCloud


def test_get_all_point_cloud(test_client, dbsession, projects_fixture, point_cloud_fixture):
    u1 = dbsession.query(User).get(1)
    resp = test_client.get('/projects/1/point-cloud/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1


def test_get_point_cloud(test_client, dbsession, projects_fixture, point_cloud_fixture):
    u1 = dbsession.query(User).get(1)
    resp = test_client.get('/projects/1/point-cloud/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200


def test_create_point_cloud(test_client, dbsession, projects_fixture):
    u1 = dbsession.query(User).get(1)
    data = {'description': "new description", 'conversion_parameters': "--scale 5.0"}
    resp = test_client.post(
        '/projects/1/point-cloud/',
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_update_point_cloud(test_client, dbsession, projects_fixture, point_cloud_fixture, convert_to_potree_mock):
    u1 = dbsession.query(User).get(1)
    data = {'description': "new description", 'conversion_parameters': "--scale 5.0"}
    resp = test_client.put(
        '/projects/1/point-cloud/1/',
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_delete_point_cloud(test_client, dbsession, projects_fixture, point_cloud_fixture):
    u1 = dbsession.query(User).get(1)
    resp = test_client.delete('/projects/1/point-cloud/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    point_cloud = dbsession.query(PointCloud).get(1)
    assert point_cloud is None


def test_upload_lidar(test_client, dbsession, projects_fixture, point_cloud_fixture,
                      lidar_las1pt2_file_fixture, convert_to_potree_mock):
    u1 = dbsession.query(User).get(1)
    resp = test_client.post(
        '/projects/1/point-cloud/1/',
        data={"file": lidar_las1pt2_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200
    convert_to_potree_mock.apply_async.assert_called_once()