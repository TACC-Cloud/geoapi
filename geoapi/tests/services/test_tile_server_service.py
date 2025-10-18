from geoapi.services.features import FeaturesService, TileService
from geoapi.models import TileServer


def test_create_tile_server(projects_fixture, db_session):
    data = {
        "name": "Test",
        "type": "tms",
        "url": "www.test.com",
        "attribution": "contributors",
    }

    tile_server = TileService.addTileServer(
        database_session=db_session, projectId=projects_fixture.id, data=data
    )
    assert tile_server.name == "Test"
    assert tile_server.type == "tms"
    assert tile_server.url == "www.test.com"
    assert tile_server.attribution == "contributors"


def test_remove_tile_server(projects_fixture, db_session):
    data = {
        "name": "Test",
        "type": "tms",
        "url": "www.test.com",
        "attribution": "contributors",
    }

    tile_server = TileService.addTileServer(
        database_session=db_session, projectId=projects_fixture.id, data=data
    )
    TileService.deleteTileServer(db_session, tile_server.id)

    assert db_session.query(TileServer).count() == 0


def test_update_tile_server(projects_fixture, db_session):
    data = {
        "name": "Test",
        "type": "tms",
        "url": "www.test.com",
        "attribution": "contributors",
    }

    TileService.addTileServer(
        database_session=db_session, projectId=projects_fixture.id, data=data
    )

    updated_data = {
        "name": "NewTestName",
    }

    updated_tile_server = TileService.updateTileServer(
        database_session=db_session, tileServerId=1, data=updated_data
    )
    assert updated_tile_server.name == "NewTestName"


def test_update_tile_servers(projects_fixture, db_session):
    data = {
        "name": "Test",
        "type": "tms",
        "url": "www.test.com",
        "attribution": "contributors",
    }

    resp1 = TileService.addTileServer(
        db_session, projectId=projects_fixture.id, data=data
    )
    resp2 = TileService.addTileServer(
        db_session, projectId=projects_fixture.id, data=data
    )

    updated_data = [
        {"id": resp1.id, "name": "NewTestName1"},
        {"id": resp2.id, "name": "NewTestName2"},
    ]

    updated_tile_server_list = TileService.updateTileServers(
        database_session=db_session, dataList=updated_data
    )

    assert updated_tile_server_list[0].name == "NewTestName1"
    assert updated_tile_server_list[1].name == "NewTestName2"


def test_create_tile_server_from_file(
    projects_fixture, tile_server_ini_file_fixture, db_session
):
    tile_server = FeaturesService.fromINI(
        db_session, projects_fixture.id, tile_server_ini_file_fixture, metadata={}
    )

    assert tile_server.name == "Base OSM"
    assert tile_server.type == "tms"
    assert tile_server.url == "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert (
        tile_server.attribution
        == "OpenStreetMap contributorshttps://www.openstreetmap.org/copyright"
    )
