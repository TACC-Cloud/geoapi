from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models import TileServer


def _get_tile_server_data():
    data = {
        "name": "Test",
        "type": "tms",
        "url": "www.test.com",
        "attribution": "contributors",
    }

    return data


# TODO add tile server listing and public listing test


def test_add_tile_server(test_client, projects_fixture):
    u1 = db_session.get(User, 1)

    resp = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["name"] == "Test"
    assert data["type"] == "tms"
    assert data["url"] == "www.test.com"
    assert data["attribution"] == "contributors"


def test_delete_tile_server(test_client, projects_fixture):
    u1 = db_session.get(User, 1)
    test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    resp = test_client.delete(
        "/projects/1/tile-servers/1/", headers={"X-Tapis-Token": u1.jwt}
    )
    assert resp.status_code == 200
    proj = db_session.get(TileServer, 1)
    assert proj is None


def test_update_tile_server(test_client, projects_fixture):
    u1 = db_session.get(User, 1)

    resp = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    data = {
        "name": "NewTestName",
    }

    resp = test_client.put(
        "/projects/1/tile-servers/1/", json=data, headers={"X-Tapis-Token": u1.jwt}
    )

    assert resp.status_code == 200
    tsv = db_session.get(TileServer, 1)
    assert tsv.name == "NewTestName"


def test_update_tile_servers(test_client, projects_fixture):
    u1 = db_session.get(User, 1)

    resp1 = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    resp2 = test_client.post(
        "/projects/1/tile-servers/",
        json=_get_tile_server_data(),
        headers={"X-Tapis-Token": u1.jwt},
    )

    updated_data = [
        {"id": resp1.get_json()["id"], "name": "NewTestName1"},
        {"id": resp2.get_json()["id"], "name": "NewTestName2"},
    ]

    resp = test_client.put(
        "/projects/1/tile-servers/",
        json=updated_data,
        headers={"X-Tapis-Token": u1.jwt},
    )

    assert resp.status_code == 200

    my_tsv1 = db_session.get(TileServer, 1)
    assert my_tsv1.name == "NewTestName1"

    my_tsv2 = db_session.get(TileServer, 2)
    assert my_tsv2.name == "NewTestName2"


def test_import_tile_server__tapis(
    test_client, projects_fixture, import_file_from_tapis_mock
):
    u1 = db_session.get(User, 1)
    resp = test_client.post(
        "/projects/1/features/files/import/",
        json={
            "files": [{"system": "designsafe.storage.default", "path": "metadata.ini"}]
        },
        headers={"X-Tapis-Token": u1.jwt},
    )
    assert resp.status_code == 200
