"""
Objects (features, point clouds, tile servers) can only be reached through the
project they belong to. Using another project's object ID returns 404 and
changes nothing.
"""

import json
import os
import shutil

import pytest

from geoapi.models import Feature, PointCloud, Project, TileServer, User
from geoapi.services.point_cloud import PointCloudService
from geoapi.services.tile_server import TileService
from geoapi.utils.assets import get_project_asset_dir


@pytest.fixture(scope="function")
def other_project_fixture(user2, db_session):
    """Private project that only user2 is a member of (user1 has no access)"""
    project = Project(name="other", description="other project")
    project.users.append(user2)
    project.tenant_id = user2.tenant_id
    db_session.add(project)
    db_session.commit()
    yield project

    shutil.rmtree(get_project_asset_dir(project.id), ignore_errors=True)


@pytest.fixture(scope="function")
def other_feature_fixture(other_project_fixture, db_session):
    home = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(home, "fixtures/properties.json"), "rb") as f:
        feat = Feature.fromGeoJSON(json.loads(f.read()))
    feat.project_id = other_project_fixture.id
    db_session.add(feat)
    db_session.commit()
    yield feat


@pytest.fixture(scope="function")
def other_point_cloud_fixture(other_project_fixture, user2, db_session):
    yield PointCloudService.create(
        db_session,
        projectId=other_project_fixture.id,
        data={"description": "other description"},
        user=user2,
    )


@pytest.fixture(scope="function")
def other_tile_server_fixture(other_project_fixture, db_session):
    yield TileService.addTileServer(
        db_session,
        other_project_fixture.id,
        {"name": "Other", "type": "tms", "url": "www.other.com", "attribution": "a"},
    )


@pytest.fixture(scope="function")
def own_tile_server_fixture(projects_fixture, db_session):
    yield TileService.addTileServer(
        db_session,
        projects_fixture.id,
        {"name": "Own", "type": "tms", "url": "www.own.com", "attribution": "a"},
    )


def _user1(db_session):
    return db_session.get(User, 1)


# Features


def test_get_feature_from_other_project(
    test_client, projects_fixture, other_feature_fixture, db_session
):
    resp = test_client.get(
        f"/projects/{projects_fixture.id}/features/{other_feature_fixture.id}/",
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404


def test_get_feature_from_other_project_via_public_project(
    test_client, public_projects_fixture, other_feature_fixture
):
    # Anonymous user, public project in the URL, feature from a private project
    resp = test_client.get(
        f"/projects/{public_projects_fixture.id}/features/{other_feature_fixture.id}/"
    )
    assert resp.status_code == 404


def test_get_feature_in_public_project(
    test_client, public_projects_fixture, feature_fixture
):
    resp = test_client.get(
        f"/projects/{public_projects_fixture.id}/features/{feature_fixture.id}/"
    )
    assert resp.status_code == 200


def test_delete_feature_from_other_project(
    test_client, projects_fixture, other_feature_fixture, db_session
):
    feature_id = other_feature_fixture.id
    resp = test_client.delete(
        f"/projects/{projects_fixture.id}/features/{feature_id}/",
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404
    db_session.expire_all()
    assert db_session.get(Feature, feature_id) is not None


def test_get_streetview_sequence_from_other_project_feature(
    test_client, projects_fixture, other_feature_fixture, db_session
):
    resp = test_client.get(
        f"/projects/{projects_fixture.id}/streetview/{other_feature_fixture.id}/",
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404


# Point clouds


def test_get_point_cloud_from_other_project(
    test_client, projects_fixture, other_point_cloud_fixture, db_session
):
    resp = test_client.get(
        f"/projects/{projects_fixture.id}/point-cloud/{other_point_cloud_fixture.id}/",
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404


def test_get_point_cloud_from_other_project_via_public_project(
    test_client, public_projects_fixture, other_point_cloud_fixture
):
    resp = test_client.get(
        f"/projects/{public_projects_fixture.id}/point-cloud/"
        f"{other_point_cloud_fixture.id}/"
    )
    assert resp.status_code == 404


def test_update_point_cloud_ignores_protected_fields(
    test_client, projects_fixture, other_project_fixture, db_session, user1
):
    point_cloud = PointCloudService.create(
        db_session, projectId=projects_fixture.id, data={}, user=user1
    )
    point_cloud_id = point_cloud.id
    resp = test_client.put(
        f"/projects/{projects_fixture.id}/point-cloud/{point_cloud_id}/",
        json={
            "description": "new description",
            "id": 999,
            "project_id": other_project_fixture.id,
        },
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 200
    db_session.expire_all()
    point_cloud = db_session.get(PointCloud, point_cloud_id)
    assert point_cloud.description == "new description"
    assert point_cloud.project_id == projects_fixture.id


# Tile servers


def test_update_tile_server_from_other_project(
    test_client, projects_fixture, other_tile_server_fixture, db_session
):
    tile_server_id = other_tile_server_fixture.id
    resp = test_client.put(
        f"/projects/{projects_fixture.id}/tile-servers/{tile_server_id}/",
        json={"name": "Changed"},
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404
    db_session.expire_all()
    assert db_session.get(TileServer, tile_server_id).name == "Other"


def test_delete_tile_server_from_other_project(
    test_client, projects_fixture, other_tile_server_fixture, db_session
):
    tile_server_id = other_tile_server_fixture.id
    resp = test_client.delete(
        f"/projects/{projects_fixture.id}/tile-servers/{tile_server_id}/",
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404
    db_session.expire_all()
    assert db_session.get(TileServer, tile_server_id) is not None


def test_update_tile_servers_with_other_project_id_changes_nothing(
    test_client,
    projects_fixture,
    own_tile_server_fixture,
    other_tile_server_fixture,
    db_session,
):
    own_id = own_tile_server_fixture.id
    other_id = other_tile_server_fixture.id
    resp = test_client.put(
        f"/projects/{projects_fixture.id}/tile-servers/",
        json=[
            {"id": own_id, "name": "Changed"},
            {"id": other_id, "name": "Changed"},
        ],
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404
    db_session.expire_all()
    assert db_session.get(TileServer, own_id).name == "Own"
    assert db_session.get(TileServer, other_id).name == "Other"


def test_update_tile_servers_without_id(
    test_client, projects_fixture, own_tile_server_fixture, db_session
):
    resp = test_client.put(
        f"/projects/{projects_fixture.id}/tile-servers/",
        json=[{"name": "Changed"}],
        headers={"X-Tapis-Token": _user1(db_session).jwt},
    )
    assert resp.status_code == 404
