import pytest

from geoapi.db import db_session

from geoapi.services.projects import ProjectsService
from geoapi.models import User, observable_data
from geoapi.exceptions import ObservableProjectAlreadyExists


def test_create_project():
    user = db_session.query(User).get(1)
    data = {
        'project': {
            'name': "test name",
            'description': "test description",
        },
    }
    proj = ProjectsService.create(data, user)
    assert proj.id is not None
    assert len(proj.users) == 1
    assert proj.name == "test name"
    assert proj.description == "test description"


def test_create_observable_project(userdata,
                                   get_system_users_mock,
                                   agave_utils_with_geojson_file_mock,
                                   import_from_agave_mock):
    user = db_session.query(User).get(1)
    data = {
        'project': {
            'name': 'Renamed Project',
            'description': 'New Description',
            'system_id': 'system',
            'system_path': '/path',
            'system_file': 'file_name'
        },
        'observable': True,
        'watch_content': True
    }

    proj = ProjectsService.create(data, user)
    assert len(proj.users) == 2


def test_create_observable_project_already_exists(observable_projects_fixture,
                                                  agave_utils_with_geojson_file_mock,
                                                  import_from_agave_mock,
                                                  get_system_users_mock):
    user = db_session.query(User).get(1)
    data = {
        'project': {
            'name': 'Renamed Project',
            'description': 'New Description',
            'system_id': observable_projects_fixture.system_id,
            'system_path': observable_projects_fixture.path,
            'system_file': 'file_name'
        },
        'observable': True,
        'watch_content': True
    }

    with pytest.raises(ObservableProjectAlreadyExists):
        ProjectsService.create(data, user)


def test_get_with_project_id(projects_fixture):
    project = ProjectsService.get(project_id=projects_fixture.id)
    assert project.id == projects_fixture.id


def test_get_with_uid(projects_fixture):
    project = ProjectsService.get(uuid=projects_fixture.uuid)
    assert project.uuid == projects_fixture.uuid


def test_get_missing_argument(projects_fixture):
    with pytest.raises(ValueError):
        ProjectsService.get()


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


def test_update_project(projects_fixture):
    user = db_session.query(User).get(1)
    data = {
        'project': {
            'name': 'new name',
            'description': 'new description',
        },
    }
    proj = ProjectsService.update(user, projects_fixture.id, data)
    assert proj.name == "new name"
    assert proj.description == "new description"
