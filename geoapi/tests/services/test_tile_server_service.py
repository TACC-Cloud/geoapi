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


def test_update_tile_server_merges_jsonb_fields(projects_fixture, db_session):
    """Test that updating a tile server merges JSONB fields instead of replacing them.

    Tests both adding new keys and updating existing keys in JSONB fields.
    """
    data = {
        "name": "Test",
        "type": "tms",
        "url": "www.test.com",
        "attribution": "contributors",
        "tileOptions": {
            "bounds": [-180, -90, 180, 90],
            "minZoom": 0,
            "maxZoom": 18,  # Will be updated
        },
        "uiOptions": {
            "opacity": 1.0,
            "isActive": True,
        },
    }

    tile_server = TileService.addTileServer(
        database_session=db_session, projectId=projects_fixture.id, data=data
    )

    # Update existing maxZoom, add new zIndex
    updated_data = {
        "tileOptions": {"maxZoom": 20},  # Updating existing key
        "uiOptions": {"zIndex": -1},  # Adding new key
    }

    updated_tile_server = TileService.updateTileServer(
        database_session=db_session, tileServerId=tile_server.id, data=updated_data
    )

    # Verify tileOptions: bounds and minZoom preserved, maxZoom updated
    assert updated_tile_server.tileOptions["bounds"] == [-180, -90, 180, 90]
    assert updated_tile_server.tileOptions["minZoom"] == 0
    assert updated_tile_server.tileOptions["maxZoom"] == 20  # Updated from 18

    # Verify uiOptions: existing fields preserved, new field added
    assert updated_tile_server.uiOptions["opacity"] == 1.0
    assert updated_tile_server.uiOptions["isActive"] is True
    assert updated_tile_server.uiOptions["zIndex"] == -1  # New field


def test_update_tile_servers_merges_jsonb_fields(projects_fixture, db_session):
    """Test that batch updating tile servers merges JSONB fields instead of replacing them.

    This simulates the common use case where the frontend reorders layers (zIndex)
    and adjusts visibility settings (opacity) without sending tileOptions data.
    """
    data1 = {
        "name": "Layer1",
        "type": "tms",
        "url": "www.test1.com",
        "attribution": "contributors",
        "tileOptions": {
            "bounds": [-180, -90, 180, 90],
            "minZoom": 0,
        },
        "uiOptions": {
            "opacity": 1.0,
            "isActive": True,
            "showDescription": False,
        },
    }

    data2 = {
        "name": "Layer2",
        "type": "tms",
        "url": "www.test2.com",
        "attribution": "contributors",
        "tileOptions": {
            "bounds": [-100, -50, 100, 50],
            "minZoom": 2,
            "maxZoom": 18,
        },
        "uiOptions": {
            "opacity": 0.8,
            "isActive": False,
            "showDescription": True,
        },
    }

    resp1 = TileService.addTileServer(db_session, projects_fixture.id, data1)
    resp2 = TileService.addTileServer(db_session, projects_fixture.id, data2)

    # Update zIndex and opacity in uiOptions (common use case: reordering and adjusting visibility)
    # Note: tileOptions is NOT sent, and other uiOptions fields are NOT sent
    updated_data = [
        {"id": resp1.id, "uiOptions": {"zIndex": -1, "opacity": 0.9}},
        {"id": resp2.id, "uiOptions": {"zIndex": -2, "opacity": 0.5}},
    ]

    updated_tile_servers = TileService.updateTileServers(
        database_session=db_session, dataList=updated_data
    )

    # Verify first tile server: tileOptions completely preserved
    assert updated_tile_servers[0].tileOptions["bounds"] == [-180, -90, 180, 90]
    assert updated_tile_servers[0].tileOptions["minZoom"] == 0

    # Verify first tile server: uiOptions merged (updated fields + preserved fields)
    assert updated_tile_servers[0].uiOptions["zIndex"] == -1  # Updated
    assert updated_tile_servers[0].uiOptions["opacity"] == 0.9  # Updated
    assert updated_tile_servers[0].uiOptions["isActive"] is True  # Preserved
    assert updated_tile_servers[0].uiOptions["showDescription"] is False  # Preserved

    # Verify second tile server: tileOptions completely preserved
    assert updated_tile_servers[1].tileOptions["bounds"] == [-100, -50, 100, 50]
    assert updated_tile_servers[1].tileOptions["minZoom"] == 2
    assert updated_tile_servers[1].tileOptions["maxZoom"] == 18

    # Verify second tile server: uiOptions merged (updated fields + preserved fields)
    assert updated_tile_servers[1].uiOptions["zIndex"] == -2  # Updated
    assert updated_tile_servers[1].uiOptions["opacity"] == 0.5  # Updated
    assert updated_tile_servers[1].uiOptions["isActive"] is False  # Preserved
    assert updated_tile_servers[1].uiOptions["showDescription"] is True  # Preserved


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
