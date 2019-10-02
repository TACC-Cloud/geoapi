import os

from werkzeug.datastructures import FileStorage

from geoapi.services.features import FeaturesService
from geoapi.models import Feature, FeatureAsset
from geoapi.utils.assets import get_project_asset_dir


def test_insert_feature_geojson(dbsession, projects_fixture, feature_properties_file_fixture):
    features = FeaturesService.fromGeoJSON(projects_fixture.id, feature_properties_file_fixture, metadata={})
    feature = features[0]
    assert len(features) == 1
    assert feature.project_id == projects_fixture.id
    assert dbsession.query(Feature).count() == 1
    assert dbsession.query(FeatureAsset).count() == 0

def test_insert_feature_collection(dbsession, projects_fixture, geojson_file_fixture):
    features = FeaturesService.fromGeoJSON(projects_fixture.id, geojson_file_fixture, metadata={})
    for feature in features:
        assert feature.project_id == projects_fixture.id
    assert dbsession.query(Feature).count() == 3
    assert dbsession.query(FeatureAsset).count() == 0

def test_remove_feature(dbsession, projects_fixture, feature_fixture):
    FeaturesService.delete(feature_fixture.id)
    assert dbsession.query(Feature).count() == 0
    assert not os.path.exists(get_project_asset_dir(feature_fixture.project_id))

def test_create_feature_image(dbsession, projects_fixture, image_file_fixture):
    feature = FeaturesService.fromImage(projects_fixture.id, image_file_fixture, metadata={})
    assert feature.project_id == projects_fixture.id
    assert len(feature.assets) == 1
    assert dbsession.query(Feature).count() == 1
    assert dbsession.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 2
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".jpeg"))
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".thumb.jpeg"))

def test_remove_feature_image(dbsession, projects_fixture, image_file_fixture):
    feature = FeaturesService.fromImage(projects_fixture.id, image_file_fixture, metadata={})
    FeaturesService.delete(feature.id)

    assert dbsession.query(Feature).count() == 0
    assert dbsession.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0

def test_create_feature_image_asset(dbsession, projects_fixture, feature_fixture, image_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(image_file_fixture))
    assert feature.id == feature_fixture.id
    assert len(feature.assets) == 1
    assert dbsession.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 2
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".jpeg"))
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".thumb.jpeg"))


def test_remove_feature_image_asset(dbsession, projects_fixture, feature_fixture, image_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(image_file_fixture))
    FeaturesService.delete(feature.id)
    assert dbsession.query(Feature).count() == 0
    assert dbsession.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0

def test_create_feature_video_asset(dbsession, projects_fixture, feature_fixture, video_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(video_file_fixture))
    assert feature.id == feature_fixture.id
    assert len(feature.assets) == 1
    assert dbsession.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 1
    os.path.isfile(os.path.join(get_project_asset_dir(projects_fixture.id), str(feature.assets[0].uuid) + ".mp4"))


def test_remove_feature_video_asset(dbsession, projects_fixture, feature_fixture, video_file_fixture):
    feature = FeaturesService.createFeatureAsset(projects_fixture.id,
                                                 feature_fixture.id,
                                                 FileStorage(video_file_fixture))
    FeaturesService.delete(feature.id)
    assert dbsession.query(Feature).count() == 0
    assert dbsession.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0

