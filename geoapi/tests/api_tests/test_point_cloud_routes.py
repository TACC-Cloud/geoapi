from geoapi.models import User, PointCloud
from geoapi.db import db_session
from unittest.mock import patch


def test_get_all_point_cloud(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.get(User, 1)
    resp = test_client.get(
        "/projects/1/point-cloud/", headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1


def test_get_point_cloud(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.get(User, 1)
    resp = test_client.get(
        "/projects/1/point-cloud/1/", headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 200


def test_get_point_cloud_public_access(
    test_client, public_projects_fixture, point_cloud_fixture
):
    resp = test_client.get("/projects/1/point-cloud/1/")
    assert resp.status_code == 200


def test_create_point_cloud(test_client, projects_fixture):
    u1 = db_session.get(User, 1)
    data = {"description": "new description", "conversion_parameters": "--scale 5.0"}
    resp = test_client.post(
        "/projects/1/point-cloud/", json=data, headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 200


def test_update_point_cloud(
    test_client, projects_fixture, point_cloud_fixture, convert_to_potree_mock
):
    u1 = db_session.get(User, 1)
    data = {"description": "new description", "conversion_parameters": "--scale 5.0"}
    resp = test_client.put(
        "/projects/1/point-cloud/1/", json=data, headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 200


def test_delete_point_cloud(test_client, projects_fixture, point_cloud_fixture):
    u1 = db_session.get(User, 1)
    resp = test_client.delete(
        "/projects/1/point-cloud/1/", headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 200
    point_cloud = db_session.get(PointCloud, 1)
    assert point_cloud is None


@patch("geoapi.tasks.external_data.import_point_clouds_from_tapis")
def test_import_lidar_tapis(
    import_point_clouds_from_tapis_mock,
    test_client,
    projects_fixture,
    point_cloud_fixture,
):
    u1 = db_session.get(User, 1)
    resp = test_client.post(
        "/projects/1/point-cloud/1/import/",
        json={"files": [{"system": "designsafe.storage.default", "path": "file.LAS"}]},
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 200
    import_point_clouds_from_tapis_mock.delay.assert_called_once()


def test_import_lidar_tapis_wrong_file(
    test_client, projects_fixture, point_cloud_fixture
):
    u1 = db_session.get(User, 1)
    resp = test_client.post(
        "/projects/1/point-cloud/1/import/",
        json={"files": [{"system": "designsafe.storage.default", "path": "file.jpg"}]},
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 400
    assert "Invalid file type for point clouds." in resp.json["message"]
