import pytest
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService


def test_user_get(users_fixture):
    user = UserService.getUser("test1")
    assert user.id is not None
    assert user.created is not None


def test_user_create(users_fixture):
    user = UserService.create("newUser")
    assert user.id is not None
    assert user.created is not None
    assert user.username == 'newUser'

def test_projects_for_user(users_fixture):
    user = UserService.getUser("test1")
    data = {
        "name": 'new project',
        'description': 'test'
    }
    ProjectsService.create(data, user)
    myProjects = UserService.projectsForUser(user.username)
    assert len(myProjects) == 1
    assert myProjects[0].name == 'new project'