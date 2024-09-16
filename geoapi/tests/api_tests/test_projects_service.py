import pytest

from geoapi.db import db_session

from geoapi.services.projects import ProjectsService
from geoapi.models import User
from geoapi.models.project import Project, ProjectUser
from geoapi.exceptions import ProjectSystemPathWatchFilesAlreadyExists


def test_create_project(user1):
    data = {
        'name': "test name",
        'description': "test description",
    }
    project = ProjectsService.create(db_session, data, user1)
    assert project.id is not None
    assert len(project.users) == 1
    assert project.name == "test name"
    assert project.description == "test description"
    assert project.deletable
    assert not project.public
    assert not project.watch_users
    assert not project.watch_content
    assert project.project_users[0].user_id == user1.id
    assert project.project_users[0].creator
    assert not project.project_users[0].admin


def test_delete_project(projects_fixture, remove_project_assets_mock, user1):
    ProjectsService.delete(db_session, user1, projects_fixture.id)
    projects = db_session.query(Project).all()
    assert projects == []


def test_create_watch_users_watch_content_project(user1,
                                                  get_system_users_mock,
                                                  agave_utils_with_geojson_file_mock,
                                                  import_from_agave_mock):
    data = {
        'name': 'test name',
        'description': 'test description',
        'system_id': 'system',
        'system_path': '/path',
        'system_file': 'file_name',
        'watch_users': True,
        'watch_content': True
    }
    project = ProjectsService.create(db_session, data, user1)
    assert project.id is not None
    assert len(project.users) == 2
    assert project.name == "test name"
    assert project.description == "test description"
    assert project.deletable
    assert not project.public
    assert project.watch_users
    assert project.watch_content

    creator_user = db_session.query(ProjectUser).filter(ProjectUser.user_id == user1.id).one()
    assert creator_user.creator
    assert creator_user.admin

    other_user = db_session.query(ProjectUser).filter(ProjectUser.user_id != user1.id).one()
    assert not other_user.creator
    assert not other_user.admin


def test_create_watch_content_project_already_exists(watch_content_users_projects_fixture,
                                                     agave_utils_with_geojson_file_mock,
                                                     import_from_agave_mock,
                                                     get_system_users_mock):
    user = db_session.query(User).get(1)
    data = {
        'name': 'test name',
        'description': 'test description',
        'system_id': watch_content_users_projects_fixture.system_id,
        'system_path': watch_content_users_projects_fixture.system_path,
        'system_file': 'file_name',
        'watch_users': True,
        'watch_content': True
    }

    with pytest.raises(ProjectSystemPathWatchFilesAlreadyExists):
        ProjectsService.create(db_session, data, user)


def test_get_with_project_id(projects_fixture):
    project = ProjectsService.get(database_session=db_session, project_id=projects_fixture.id)
    assert project.id == projects_fixture.id


def test_get_with_uid(projects_fixture):
    project = ProjectsService.get(database_session=db_session, uuid=projects_fixture.uuid)
    assert project.uuid == projects_fixture.uuid


def test_get_missing_argument(projects_fixture):
    with pytest.raises(ValueError):
        ProjectsService.get(db_session)


def test_get_features(projects_fixture, feature_fixture):
    project_features = ProjectsService.getFeatures(db_session, projects_fixture.id)
    assert len(project_features['features']) == 1


def test_get_features_filter_type(projects_fixture,
                                  feature_fixture,
                                  image_feature_fixture):
    project_features = ProjectsService.getFeatures(db_session, projects_fixture.id)
    assert len(project_features['features']) == 2

    query = {'assetType': 'image'}
    project_features = ProjectsService.getFeatures(db_session, projects_fixture.id, query)
    assert len(project_features['features']) == 1

    query = {'assetType': 'video'}
    project_features = ProjectsService.getFeatures(db_session, projects_fixture.id, query)
    assert len(project_features['features']) == 0


def test_update_project(projects_fixture):
    data = {
        'name': 'new name',
        'description': 'new description'
    }
    proj = ProjectsService.update(db_session, projects_fixture.id, data)
    assert proj.name == "new name"
    assert proj.description == "new description"
