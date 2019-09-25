import os
import glob

from geoapi.services.projects import ProjectsService
from geoapi.services.features import FeaturesService
from geoapi.models import User, Feature, FeatureAsset
from geoapi.utils.assets import get_asset_dir


def test_create_project(dbsession):
    user = dbsession.query(User).get(1)
    data = {
        "name": "test name",
        "description": "test description"
    }
    proj = ProjectsService.create(data, user)
    assert proj.id is not None
    assert len(proj.users) == 1
    assert proj.name == "test name"

def test_insert_feature_geojson():
    pass

def test_insert_feature_collection():
    pass

def test_create_image_feature(dbsession, projects_fixture, image_file_fixture):
    feature = FeaturesService.fromImage(projects_fixture.id, image_file_fixture, metadata={})
    assert feature.project_id == projects_fixture.id
    assert len(feature.assets) == 1
    assert len(glob.glob('{}/{}*.jpeg'.format(get_asset_dir(projects_fixture.id), feature.assets[0].uuid))) == 2

def test_remove_image_feature(dbsession, projects_fixture, image_file_fixture):
    feature = FeaturesService.fromImage(projects_fixture.id, image_file_fixture, metadata={})
    FeaturesService.delete(feature.id)

    assert dbsession.query(Feature).count() == 0
    assert dbsession.query(FeatureAsset).count() == 0
    assert len(os.listdir(get_asset_dir(feature.project_id))) == 0

def test_remove_feature():
    pass

def test_remove_feature_removes_assets():
    pass

