from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.exceptions import ApiException
from geoapi.models.project import ProjectUser
from geoapi.db import db_session
import pytest


def test_user_get(userdata):
    user = UserService.getUser(db_session, "test1", "test")
    assert user.id is not None
    assert user.created is not None


def test_user_create(userdata):
    user = UserService.create(database_session=db_session, username="newUser", jwt="testjwt", tenant="test")
    assert user.id is not None
    assert user.created is not None
    assert user.username == 'newUser'
    assert user.jwt == "testjwt"


def test_projects_for_user(user1):
    data = {
        'name': 'new project',
        'description': 'test'
    }
    ProjectsService.create(db_session, data, user1)
    my_projects = ProjectsService.list(db_session, user1)
    assert len(my_projects) == 1
    assert my_projects[0].name == 'new project'


def test_add_new_user_to_project(user1):
    data = {
        'name': 'new project',
        'description': 'test'
    }
    proj = ProjectsService.create(db_session, data, user1)
    ProjectsService.addUserToProject(db_session, proj.id, "newUser", admin=False)
    proj = ProjectsService.get(database_session=db_session, project_id=proj.id)
    assert len(proj.users) == 2


def test_add_existing_user_to_project(user1, user2, projects_fixture):
    assert not UserService.canAccess(db_session, user2, projects_fixture.id)

    ProjectsService.addUserToProject(database_session=db_session, projectId=projects_fixture.id, username=user2.username, admin=False)
    assert UserService.canAccess(db_session, user2, projects_fixture.id)
    project_user = db_session.query(ProjectUser).filter(ProjectUser.project_id == projects_fixture.id) \
        .filter(ProjectUser.user_id == user2.id).one_or_none()
    assert project_user.admin is False
    assert UserService.canAccess(db_session, user1, projects_fixture.id)


def test_add_existing_user_to_project_as_admin(user1, user2, projects_fixture):
    assert not UserService.canAccess(db_session, user2, projects_fixture.id)

    ProjectsService.addUserToProject(database_session=db_session, projectId=projects_fixture.id, username=user2.username, admin=True)
    assert UserService.canAccess(db_session, user2, projects_fixture.id)
    project_user = db_session.query(ProjectUser).filter(ProjectUser.project_id == projects_fixture.id) \
        .filter(ProjectUser.user_id == user2.id).one_or_none()
    assert project_user.admin is True
    assert UserService.canAccess(db_session, user1, projects_fixture.id)


def test_remove_user(projects_fixture):
    ProjectsService.addUserToProject(db_session, projects_fixture.id, "newUser", admin=False)
    assert len(projects_fixture.users) == 2
    ProjectsService.removeUserFromProject(db_session, projects_fixture.id, "newUser")
    assert len(projects_fixture.users) == 1


def test_remove_missing_user_failure(projects_fixture):
    ProjectsService.addUserToProject(db_session, projects_fixture.id, "newUser", admin=False)
    assert len(projects_fixture.users) == 2
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(db_session, projects_fixture.id,
                                              "someOtherUser")
    assert len(projects_fixture.users) == 2


def test_remove_user_with_only_one_user_failure(projects_fixture):
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(db_session, projects_fixture.id, "test1")
    assert len(projects_fixture.users) == 1


def test_remove_user_from_observable_project(observable_projects_fixture):
    project = observable_projects_fixture.project

    ProjectsService.addUserToProject(db_session, project.id, "newUser", admin=False)
    assert len(project.users) == 2
    ProjectsService.removeUserFromProject(db_session, project.id, "newUser")
    assert len(project.users) == 1


def test_remove_last_user_with_jwt_from_observable_project_failure(
        observable_projects_fixture):
    project = observable_projects_fixture.project

    ProjectsService.addUserToProject(db_session, project.id, "newUser", admin=False)
    assert len(project.users) == 2
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(db_session,
                                              project.id,
                                              project.users[0].username)
    assert len(project.users) == 2
