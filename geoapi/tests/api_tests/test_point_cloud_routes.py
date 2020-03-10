from geoapi.models import User, PointCloud
from geoapi.db import db_session

def test_get_all_point_cloud(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/point-cloud/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1


def test_get_point_cloud(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.get('/projects/1/point-cloud/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200


def test_create_point_cloud(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    data = {'description': "new description", 'conversion_parameters': "--scale 5.0"}
    resp = test_client.post(
        '/projects/1/point-cloud/',
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_update_point_cloud(test_client, projects_fixture, point_cloud_fixture, convert_to_potree_mock):
    u1 = db_session.query(User).get(1)
    data = {'description': "new description", 'conversion_parameters': "--scale 5.0"}
    resp = test_client.put(
        '/projects/1/point-cloud/1/',
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200


def test_delete_point_cloud(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.query(User).get(1)
    resp = test_client.delete('/projects/1/point-cloud/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    point_cloud = db_session.query(PointCloud).get(1)
    assert point_cloud is None


def test_upload_lidar(test_client, projects_fixture, point_cloud_fixture,
                      lidar_las1pt2_file_fixture, check_point_cloud_mock, get_point_cloud_info_mock,
    u1 = db_session.query(User).get(1)
    u1 = dbsession.get(1)
    resp = test_client.post(
        '/projects/1/point-cloud/1/',
        data={"file": lidar_las1pt2_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 200
    convert_to_potree_mock.apply_async.assert_called_once()


def test_upload_lidar_missing_coordinate_reference_system(test_client, dbsession, projects_fixture, point_cloud_fixture,
                                                          empty_las_file_fixture, check_point_cloud_mock_missing_crs):
    u1 = db_session.query(User).get(1)
    resp = test_client.post(
        '/projects/1/point-cloud/files/',
        data={"file": empty_las_file_fixture},
        headers={'x-jwt-assertion-test': u1.jwt}
    )
    assert resp.status_code == 400
    assert "coordinate reference system could not be found" in resp.json['message']