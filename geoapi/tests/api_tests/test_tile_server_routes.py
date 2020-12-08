from geoapi.db import db_session
from geoapi.models.users import User
from geoapi.models import TileServer

def _get_tile_server_data():
    data = {"id": 1,
            "name": "OSM",
            "type": "tms",
            "url": "png",
            "attribution": "contributors",
            "opacity": 1,
            "zIndex": 0,
            "minZoom": 0,
            "maxZoom": 19,
            "isActive": "true"}

    return data


def test_add_tile_server(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)

    resp = test_client.post('/projects/1/tile-servers/',
                            data=_get_tile_server_data(),
                            headers={'x-jwt-assertion-test': u1.jwt})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["id"] == 1
    assert data["name"] == "OSM"
    assert data["type"] == "tms"
    assert data["url"] == "png"
    assert data["attribution"] == "contributors"
    assert data["opacity"] == 1
    assert data["zIndex"] == 0
    assert data["minZoom"] == 0
    assert data["maxZoom"] == 19
    assert data["isActive"] == True

def test_delete_tile_server(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    test_client.post('/projects/1/tile-servers/',
                     data=_get_tile_server_data(),
                     headers={'x-jwt-assertion-test': u1.jwt})

    resp = test_client.delete('/projects/1/tile-servers/1/', headers={'x-jwt-assertion-test': u1.jwt})
    assert resp.status_code == 200
    proj = db_session.query(TileServer).get(1)
    assert proj is None


def test_update_tile_server(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)
    predata = {"name": "OSM",
            "type": "tms",
            "url": "png",
            "attribution": "contributors",
            "opacity": 0,
            "zIndex": 0,
            "minZoom": 0,
            "maxZoom": 19,
            "isActive": "true"}

    # resp = test_client.post('/projects/1/tile-servers/',
    #                         data=_get_tile_server_data(),
    #                         headers={'x-jwt-assertion-test': u1.jwt})

    resp = test_client.post('/projects/1/tile-servers/',
                            data=predata,
                            headers={'x-jwt-assertion-test': u1.jwt})

    data = {
        "name": "NewTestName",
        "opacity": 1,
        "zIndex": -5,
        "isActive": "false"
    }

    resp = test_client.put(
        '/projects/1/tile-servers/1/',
        json=data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )

    assert resp.status_code == 200
    tsv = db_session.query(TileServer).get(1)
    # tsv = db_session.query(TileServer).get(1)
    assert tsv.name == "NewTestName"
    assert tsv.opacity == 1
    assert tsv.zIndex == -5
    assert tsv.isActive == False

def test_update_tile_servers(test_client, projects_fixture):
    u1 = db_session.query(User).get(1)

    resp1 = test_client.post('/projects/1/tile-servers/',
                     data=_get_tile_server_data(),
                     headers={'x-jwt-assertion-test': u1.jwt})

    resp2 = test_client.post('/projects/1/tile-servers/',
                     data=_get_tile_server_data(),
                     headers={'x-jwt-assertion-test': u1.jwt})

    updated_data = [
        {
            "name": "NewTestName",
            "id": 1,
            "opacity": 1,
            "zIndex": -5,
            "isActive": "false"
        },
        {
            "name": "OtherTestName",
            "id": 2,
            "opacity": 0,
            "zIndex": -3,
            "isActive": "false"
        }
    ]

    new_resp = test_client.put(
        '/projects/1/tile-servers/',
        json=updated_data,
        headers={'x-jwt-assertion-test': u1.jwt}
    )

    my_tsv1 = db_session.query(TileServer).get(1)
    assert my_tsv1.name == "NewTestName"
    assert my_tsv1.opacity == 1
    assert my_tsv1.zIndex == -5
    assert my_tsv1.isActive == False

    my_tsv2 = db_session.query(TileServer).get(2)
    assert my_tsv2.name == "OtherTestName"
    assert my_tsv2.opacity == 0
    assert my_tsv2.zIndex == -3
    assert my_tsv2.isActive == False
