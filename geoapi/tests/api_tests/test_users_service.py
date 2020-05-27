from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService
from geoapi.exceptions import ApiException
import pytest


def test_user_get(userdata):
    user = UserService.getUser("test1", "test")
    assert user.id is not None
    assert user.created is not None


def test_user_create(userdata):
    user = UserService.create("newUser", "testjwt", "test")
    assert user.id is not None
    assert user.created is not None
    assert user.username == 'newUser'
    assert user.jwt == "testjwt"


def test_projects_for_user(userdata):
    user = UserService.getUser("test1", "test")
    data = {
        "name": 'new project',
        'description': 'test'
    }
    ProjectsService.create(data, user)
    myProjects = ProjectsService.list(user)
    assert len(myProjects) == 1
    assert myProjects[0].name == 'new project'


def test_add_new_user_to_project(userdata):
    user = UserService.getUser("test1", "test")
    data = {
        "name": 'new project',
        'description': 'test'
    }
    proj = ProjectsService.create(data, user)
    ProjectsService.addUserToProject(proj.id, "newUser")
    proj = ProjectsService.get(proj.id)
    assert len(proj.users) == 2


def test_remove_user(projects_fixture):
    ProjectsService.addUserToProject(projects_fixture.id, "newUser")
    assert len(projects_fixture.users) == 2
    ProjectsService.removeUserFromProject(projects_fixture.id, "newUser")
    assert len(projects_fixture.users) == 1


def test_remove_missing_user_failure(projects_fixture):
    ProjectsService.addUserToProject(projects_fixture.id, "newUser")
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

    ProjectsService.addUserToProject(project.id, "newUser")
    assert len(project.users) == 2
    ProjectsService.removeUserFromProject(project.id, "newUser")
    assert len(project.users) == 1


def test_remove_first_user_from_observable_project_failure(
        observable_projects_fixture):
    project = observable_projects_fixture.project

    ProjectsService.addUserToProject(project.id, "newUser")
    assert len(project.users) == 2
    with pytest.raises(ApiException):
        ProjectsService.removeUserFromProject(project.id,
                                              project.users[0].username)
    assert len(project.users) == 2
