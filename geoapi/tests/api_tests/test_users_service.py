from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.exceptions import ApiException
from geoapi.models.project import ProjectUser, Project
from geoapi.models.users import User
from geoapi.db import db_session
import pytest


def test_user_get(userdata):
    user = UserService.getUser("test1", "test")
    assert user.id is not None
    assert user.created is not None


def test_user_create(userdata):
    user = UserService.create(username="newUser", jwt="testjwt", tenant="test")
    assert user.id is not None
    assert user.created is not None
    assert user.username == 'newUser'
    assert user.jwt == "testjwt"


def test_projects_for_user(userdata):
    user = UserService.getUser("test1", "test")
    data = {
        'project': {
            'name': 'new project',
            'description': 'test'
        },
    }
    ProjectsService.create(data, user)
    myProjects = ProjectsService.list(user)
    assert len(myProjects) == 1
    assert myProjects[0].name == 'new project'


def test_add_new_user_to_project(userdata):
    user = UserService.getUser("test1", "test")
    data = {
        'project': {
            'name': 'new project',
            'description': 'test'
        },
    }
    proj = ProjectsService.create(data, user)
    ProjectsService.addUserToProject(proj.id, "newUser", admin=False)
    proj = ProjectsService.get(project_id=proj.id)
    assert len(proj.users) == 2


def test_add_existing_user_to_project(user1, user2, projects_fixture):
    assert not UserService.canAccess(user2, projects_fixture.id)

    ProjectsService.addUserToProject(projectId=projects_fixture.id, username=user2.username, admin=False)
    assert UserService.canAccess(user2, projects_fixture.id)
    project_user = db_session.query(ProjectUser).filter(Project.id == projects_fixture.id) \
        .filter(User.id == user2.id).first()
    assert project_user.admin == False
    assert UserService.canAccess(user1, projects_fixture.id)


def test_add_existing_user_to_project_as_admin(user1, user2, projects_fixture):
    assert not UserService.canAccess(user2, projects_fixture.id)

    ProjectsService.addUserToProject(projectId=projects_fixture.id, username=user2.username, admin=True)
    assert UserService.canAccess(user2, projects_fixture.id)
    project_user = db_session.query(ProjectUser).filter(Project.id == projects_fixture.id) \
        .filter(User.id == user2.id).first()
    assert project_user.admin == True
    assert UserService.canAccess(user1, projects_fixture.id)


def test_remove_user(projects_fixture):
    ProjectsService.addUserToProject(projects_fixture.id, "newUser", admin=False)
    assert len(projects_fixture.users) == 2
    ProjectsService.removeUserFromProject(projects_fixture.id, "newUser")
    assert len(projects_fixture.users) == 1


def test_remove_missing_user_failure(projects_fixture):
    ProjectsService.addUserToProject(projects_fixture.id, "newUser", admin=False)
    assert len(projects_fixture.users) == 2
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(projects_fixture.id,
                                              "someOtherUser")
    assert len(projects_fixture.users) == 2


def test_remove_user_with_only_one_user_failure(projects_fixture):
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(projects_fixture.id, "test1")
    assert len(projects_fixture.users) == 1


def test_remove_user_from_observable_project(observable_projects_fixture):
    project = observable_projects_fixture.project

    ProjectsService.addUserToProject(project.id, "newUser", admin=False)
    assert len(project.users) == 2
    ProjectsService.removeUserFromProject(project.id, "newUser")
    assert len(project.users) == 1


def test_remove_last_user_with_jwt_from_observable_project_failure(
        observable_projects_fixture):
    project = observable_projects_fixture.project

    ProjectsService.addUserToProject(project.id, "newUser", admin=False)
    assert len(project.users) == 2
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(project.id,
                                              project.users[0].username)
    assert len(project.users) == 2
