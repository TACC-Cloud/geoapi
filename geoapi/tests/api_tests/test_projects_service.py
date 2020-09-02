import pytest

from geoapi.db import db_session

from geoapi.services.projects import ProjectsService
from geoapi.models import User
from geoapi.exceptions import ObservableProjectAlreadyExists
from unittest.mock import patch


@pytest.fixture(scope="function")
def agave_utils_with_geojson_file_mock(agave_file_listings_mock, geojson_file_fixture):
    with patch('geoapi.services.projects.AgaveUtils') as MockAgaveUtils:
        MockAgaveUtils().listing.return_value = agave_file_listings_mock
        MockAgaveUtils().getFile.return_value = geojson_file_fixture
        MockAgaveUtils().systemsGet.return_value = {"id": "testSystem",
                                                    "description": "System Description"}
        yield MockAgaveUtils()


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


def test_create_observable_project_already_exists(observable_projects_fixture,
                                                  agave_utils_with_geojson_file_mock,
                                                  import_from_agave_mock):
    user = db_session.query(User).get(1)
    data = {
        "system_id": observable_projects_fixture.system_id,
        "path": observable_projects_fixture.path
    }
    with pytest.raises(ObservableProjectAlreadyExists):
        ProjectsService.createRapidProject(data, user)


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
