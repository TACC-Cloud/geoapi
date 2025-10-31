import os

from werkzeug.datastructures import FileStorage
from geoapi.services.features import FeaturesService
from geoapi.models import Feature, FeatureAsset
from geoapi.utils.assets import get_project_asset_dir, get_asset_path
from geoapi.utils.geo_location import GeoLocation


def test_create_feature_fromLatLng(projects_fixture, db_session):
    feature = FeaturesService.fromLatLng(
        db_session,
        projects_fixture.id,
        GeoLocation(latitude=10, longitude=20),
        metadata={},
    )
    assert len(feature.assets) == 0
    assert feature.id is not None


def test_hazmapperv1_file_with_images(projects_fixture, hazmpperV1_file, db_session):
    features = FeaturesService.fromGeoJSON(
        db_session, projects_fixture.id, hazmpperV1_file, metadata={}
    )
    assert len(features) == 2
    assert len(features[1].assets) == 1


def test_insert_feature_geojson(
    projects_fixture, feature_properties_file_fixture, db_session
):
    features = FeaturesService.fromGeoJSON(
        db_session, projects_fixture.id, feature_properties_file_fixture, metadata={}
    )
    feature = features[0]
    assert len(features) == 1
    assert feature.project_id == projects_fixture.id
    assert db_session.query(Feature).count() == 1
    assert db_session.query(FeatureAsset).count() == 0
    # TODO Test original_path, original_system are configured after WG-600


def test_insert_feature_collection(projects_fixture, geojson_file_fixture, db_session):
    features = FeaturesService.fromGeoJSON(
        db_session, projects_fixture.id, geojson_file_fixture, metadata={}
    )
    for feature in features:
        assert feature.project_id == projects_fixture.id
    assert db_session.query(Feature).count() == 3
    assert db_session.query(FeatureAsset).count() == 0


def test_remove_feature(projects_fixture, feature_fixture, db_session):
    FeaturesService.delete(db_session, feature_fixture.id)
    assert db_session.query(Feature).count() == 0
    assert not os.path.exists(get_project_asset_dir(feature_fixture.project_id))


def test_create_feature_image(projects_fixture, image_file_fixture, db_session):
    feature = FeaturesService.fromImage(
        db_session,
        projects_fixture.id,
        image_file_fixture,
        metadata={},
        original_system="system",
        original_path="path",
    )
    assert feature.project_id == projects_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(Feature).count() == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 2
    os.path.isfile(get_asset_path(feature.assets[0].path))
    os.path.isfile(
        os.path.join(
            get_project_asset_dir(projects_fixture.id),
            str(feature.assets[0].uuid) + ".thumb.jpeg",
        )
    )
    assert feature.assets[0].original_system == "system"
    assert feature.assets[0].original_path == "path"


def test_create_feature_image_small_image(
    projects_fixture, image_small_DES_2176_fixture, db_session
):
    feature = FeaturesService.fromImage(
        db_session, projects_fixture.id, image_small_DES_2176_fixture, metadata={}
    )
    assert feature.project_id == projects_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(Feature).count() == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 2
    os.path.isfile(get_asset_path(feature.assets[0].path))
    os.path.isfile(
        os.path.join(
            get_project_asset_dir(projects_fixture.id),
            str(feature.assets[0].uuid) + ".thumb.jpeg",
        )
    )


def test_remove_feature_image(projects_fixture, image_file_fixture, db_session):
    feature = FeaturesService.fromImage(
        db_session, projects_fixture.id, image_file_fixture, metadata={}
    )
    FeaturesService.delete(db_session, feature.id)

    assert db_session.query(Feature).count() == 0
    assert db_session.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0


def test_create_feature_image_asset(
    projects_fixture, feature_fixture, image_file_fixture, db_session
):
    feature = FeaturesService.createFeatureAsset(
        db_session,
        projects_fixture.id,
        feature_fixture.id,
        FileStorage(image_file_fixture),
        original_system="system",
        original_path="path",
    )
    assert feature.id == feature_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 2
    os.path.isfile(get_asset_path(feature.assets[0].path))
    os.path.isfile(
        os.path.join(
            get_project_asset_dir(projects_fixture.id),
            str(feature.assets[0].uuid) + ".thumb.jpeg",
        )
    )
    assert feature.assets[0].original_system == "system"
    assert feature.assets[0].original_path == "path"


def test_remove_feature_image_asset(
    projects_fixture, feature_fixture, image_file_fixture, db_session
):
    feature = FeaturesService.createFeatureAsset(
        db_session,
        projects_fixture.id,
        feature_fixture.id,
        FileStorage(image_file_fixture),
    )
    FeaturesService.delete(db_session, feature.id)
    assert db_session.query(Feature).count() == 0
    assert db_session.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0


def test_create_feature_video_asset(
    projects_fixture, feature_fixture, video_file_fixture, db_session
):
    feature = FeaturesService.createFeatureAsset(
        db_session,
        projects_fixture.id,
        feature_fixture.id,
        FileStorage(video_file_fixture),
        original_system="system",
        original_path="path",
    )
    assert feature.id == feature_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 1
    os.path.isfile(get_asset_path(feature.assets[0].path))
    os.path.isfile(
        os.path.join(
            get_project_asset_dir(projects_fixture.id),
            str(feature.assets[0].uuid) + ".mp4",
        )
    )
    assert feature.assets[0].original_system == "system"
    assert feature.assets[0].original_path == "path"


def test_remove_feature_video_asset(
    projects_fixture, feature_fixture, video_file_fixture, db_session
):
    feature = FeaturesService.createFeatureAsset(
        db_session,
        projects_fixture.id,
        feature_fixture.id,
        FileStorage(video_file_fixture),
    )
    FeaturesService.delete(db_session, feature.id)
    assert db_session.query(Feature).count() == 0
    assert db_session.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 0


def test_create_feature_shpfile(
    projects_fixture, shapefile_fixture, shapefile_additional_files_fixture, db_session
):
    features = FeaturesService.fromShapefile(
        db_session,
        projects_fixture.id,
        shapefile_fixture,
        metadata={},
        additional_files=shapefile_additional_files_fixture,
        original_path="foo",
    )
    assert len(features) == 10
    assert db_session.query(Feature).count() == 10
    assert features[0].project_id == projects_fixture.id
    # TODO Test original_path, original_system are configured after WG-600


def test_create_questionnaire_feature(
    projects_fixture, questionnaire_file_without_assets_fixture, db_session
):
    feature = FeaturesService.from_rapp_questionnaire(
        db_session,
        projects_fixture.id,
        questionnaire_file_without_assets_fixture,
        additional_files=[],
        original_system="system",
        original_path="questionnaire.rq",
    )
    assert feature.project_id == projects_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(Feature).count() == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 1
    assert len(os.listdir(get_asset_path(feature.assets[0].path))) == 1
    assert os.path.isfile(get_asset_path(feature.assets[0].path, "questionnaire.rq"))
    assert feature.assets[0].original_path == "questionnaire.rq"
    assert feature.assets[0].original_system == "system"
    assert len(os.listdir(get_asset_path(feature.assets[0].path))) == 1


def test_create_questionnaire_feature_with_assets(
    projects_fixture,
    questionnaire_file_with_assets_fixture,
    image_file_fixture,
    db_session,
):
    assets = [image_file_fixture]
    feature = FeaturesService.from_rapp_questionnaire(
        db_session,
        projects_fixture.id,
        questionnaire_file_with_assets_fixture,
        additional_files=assets,
        original_system="system",
        original_path="questionnaire.rq",
    )
    assert feature.project_id == projects_fixture.id
    assert len(feature.assets) == 1
    assert db_session.query(Feature).count() == 1
    assert db_session.query(FeatureAsset).count() == 1
    assert len(os.listdir(get_project_asset_dir(feature.project_id))) == 1
    assert len(os.listdir(get_asset_path(feature.assets[0].path))) == 3
    assert feature.assets[0].original_path == "questionnaire.rq"
    assert feature.assets[0].original_system == "system"
    assert os.path.isfile(get_asset_path(feature.assets[0].path, "questionnaire.rq"))
    assert os.path.isfile(get_asset_path(feature.assets[0].path, "image.preview.jpg"))
    assert os.path.isfile(get_asset_path(feature.assets[0].path, "image.jpg"))
