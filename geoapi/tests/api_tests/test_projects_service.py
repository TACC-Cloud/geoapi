from geoapi.db import db_session

from geoapi.services.projects import ProjectsService
from geoapi.models import User


def test_create_project():
    user = db_session.query(User).get(1)
    data = {
        "name": "test name",
        "description": "test description"
    }
    proj = ProjectsService.create(data, user)
    assert proj.id is not None
    assert len(proj.users) == 1
    assert proj.name == "test name"


def test_get_features(projects_fixture, feature_fixture):
    project_features = ProjectsService.getFeatures(projects_fixture.id)
    assert len(project_features['features']) == 1


def test_get_features_filter_type(projects_fixture,
                                  feature_fixture,
                                  image_feature_fixture):
    project_features = ProjectsService.getFeatures(projects_fixture.id)
    assert len(project_features['features']) == 2

    query = {'assetType': 'image'}
    project_features = ProjectsService.getFeatures(projects_fixture.id, query)
    assert len(project_features['features']) == 1

    query = {'assetType': 'video'}
    project_features = ProjectsService.getFeatures(projects_fixture.id, query)
    assert len(project_features['features']) == 0
