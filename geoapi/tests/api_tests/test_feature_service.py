import os

from werkzeug.datastructures import FileStorage
from geoapi.db import db_session
from geoapi.services.features import FeaturesService
from geoapi.models import Feature, FeatureAsset, TileServer
from geoapi.utils.assets import get_project_asset_dir, get_asset_path


def test_hazmapperv1_file_with_images(projects_fixture, hazmpperV1_file):
    features = FeaturesService.fromGeoJSON(projects_fixture.id, hazmpperV1_file, metadata={})
    assert len(features) == 2
    assert len(features[1].assets) == 1


def test_insert_feature_geojson(projects_fixture, feature_properties_file_fixture):
    features = FeaturesService.fromGeoJSON(projects_fixture.id, feature_properties_file_fixture, metadata={})
    feature = features[0]
    assert len(features) == 1
    assert feature.project_id == projects_fixture.id
    assert db_session.query(Feature).count() == 1
    assert db_session.query(FeatureAsset).count() == 0


def test_insert_feature_collection(projects_fixture, geojson_file_fixture):
    features = FeaturesService.fromGeoJSON(projects_fixture.id, geojson_file_fixture, metadata={})
    for feature in features:
        assert feature.project_id == projects_fixture.id
    assert db_session.query(Feature).count() == 3
    assert db_session.query(FeatureAsset).count() == 0


def test_remove_feature(projects_fixture, feature_fixture):
    FeaturesService.delete(feature_fixture.id)
    assert db_session.query(Feature).count() == 0
    assert not os.path.exists(get_project_asset_dir(feature_fixture.project_id))


def test_create_feature_image(projects_fixture, image_file_fixture):
    feature = FeaturesService.fromImage(projects_fixture.id, image_file_fixture, metadata={})
    assert feature.project_id == projects_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(Feature).count() == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 2
    os.path.isfile(get_asset_path(feature.assets[0].path))
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".thumb.jpeg"))


def test_remove_feature_image(projects_fixture, image_file_fixture):
    feature = FeaturesService.fromImage(projects_fixture.id, image_file_fixture, metadata={})
    FeaturesService.delete(feature.id)

    assert db_session.query(Feature).count() == 0
    assert db_session.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0


def test_create_feature_image_asset(projects_fixture, feature_fixture, image_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(image_file_fixture))
    assert feature.id == feature_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 2
    os.path.isfile(get_asset_path(feature.assets[0].path))
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".thumb.jpeg"))


def test_remove_feature_image_asset(projects_fixture, feature_fixture, image_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(image_file_fixture))
    FeaturesService.delete(feature.id)
    assert db_session.query(Feature).count() == 0
    assert db_session.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0


def test_create_feature_video_asset(projects_fixture, feature_fixture, video_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(video_file_fixture))
    assert feature.id == feature_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 1
    os.path.isfile(get_asset_path(feature.assets[0].path))
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".mp4"))


def test_remove_feature_video_asset(projects_fixture, feature_fixture, video_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(video_file_fixture))
    FeaturesService.delete(feature.id)
    assert db_session.query(Feature).count() == 0
    assert db_session.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0


def test_create_feature_shpfile(projects_fixture, shapefile_fixture, shapefile_additional_files_fixture):
    features = FeaturesService.fromShapefile(projects_fixture.id,
                                             shapefile_fixture,
                                             metadata={},
                                             additional_files=shapefile_additional_files_fixture,
                                             original_path="foo")
    assert len(features) == 10
    assert db_session.query(Feature).count() == 10
    assert features[0].project_id == projects_fixture.id

def test_create_tile_server(projects_fixture):
    data = {"name": "OSM",
            "type": "tms",
            "url": "png",
            "attribution": "contributors",
            "opacity": 1,
            "zIndex": 0,
            "minZoom": 0,
            "maxZoom": 19,
            "isActive": True}

    tile_server = FeaturesService.addTileServer(projectId=projects_fixture.id, metadata=data)
    assert tile_server.name == "OSM"
    assert tile_server.type == "tms"
    assert tile_server.url == "png"
    assert tile_server.attribution == "contributors"
    assert tile_server.opacity == 1
    assert tile_server.zIndex == 0
    assert tile_server.minZoom == 0
    assert tile_server.maxZoom == 19
    assert tile_server.isActive == True

def test_remove_tile_server(projects_fixture):
    data = {"name": "OSM",
            "type": "tms",
            "url": "png",
            "attribution": "contributors",
            "opacity": 1,
            "zIndex": 0,
            "minZoom": 0,
            "maxZoom": 19,
            "isActive": True}

    tile_server = FeaturesService.addTileServer(projectId=projects_fixture.id, metadata=data)
    FeaturesService.deleteTileServer(projects_fixture.id,
                                     tile_server.id)

    assert db_session.query(TileServer).count() == 0

def test_update_tile_server(projects_fixture):
    data = {"name": "OSM",
            "type": "tms",
            "url": "png",
            "attribution": "contributors",
            "opacity": 0,
            "zIndex": 0,
            "minZoom": 0,
            "maxZoom": 19,
            "isActive": True}

    tile_server = FeaturesService.addTileServer(projectId=projects_fixture.id, metadata=data)

    updated_data = {
        "name": "NewTestName",
        "opacity": 1,
        "zIndex": -5,
        "isActive": False
    }

    updated_tile_server = FeaturesService.updateTileServer(projectId=projects_fixture.id,
                                                           tileServerId=1,
                                                           data=updated_data)
    assert updated_tile_server.name == "NewTestName"
    assert updated_tile_server.opacity == 1
    assert updated_tile_server.zIndex == -5
    assert updated_tile_server.isActive == False

def test_update_tile_servers(projects_fixture):
    data = {"name": "Test1",
            "type": "tms",
            "url": "png",
            "attribution": "contributors",
            "opacity": 1,
            "zIndex": 0,
            "minZoom": 0,
            "maxZoom": 19,
            "isActive": True}

    tile_server1 = FeaturesService.addTileServer(projectId=projects_fixture.id, metadata=data)
    data['name'] = 'Test2'
    tile_server2 = FeaturesService.addTileServer(projectId=projects_fixture.id, metadata=data)

    updated_data = [
        {
            "name": "NewTestName",
            "id": tile_server1.id,
            "opacity": 0,
            "zIndex": -5,
            "isActive": False
        },
        {
            "name": "OtherTestName",
            "id": tile_server2.id,
            "opacity": 1,
            "zIndex": -3,
            "isActive": False
        }
    ]

    updated_tile_server_list = FeaturesService.updateTileServers(projectId=projects_fixture.id, dataList=updated_data)

    assert updated_tile_server_list[0].name == "NewTestName"
    assert updated_tile_server_list[0].opacity == 0
    assert updated_tile_server_list[0].zIndex == -5
    assert updated_tile_server_list[0].isActive == False

    assert updated_tile_server_list[1].name == "OtherTestName"
    assert updated_tile_server_list[1].opacity == 1
    assert updated_tile_server_list[1].zIndex == -3
    assert updated_tile_server_list[1].isActive == False

def test_create_tile_server_from_file(projects_fixture, tile_server_ini_file_fixture):
    tile_server = FeaturesService.fromINI(projects_fixture.id,
                                          tile_server_ini_file_fixture,
                                          metadata={})

    assert tile_server.name == "Base OSM"
    assert tile_server.type == "tms"
    assert tile_server.url == "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert tile_server.attribution == "OpenStreetMap contributorshttps://www.openstreetmap.org/copyright"
    assert tile_server.opacity == 1
    assert tile_server.zIndex == 0
    assert tile_server.minZoom == 0
    assert tile_server.maxZoom == 19
    assert tile_server.isActive == True
