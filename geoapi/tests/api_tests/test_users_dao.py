import pytest
from geoapi.services.users import UserService
from geoapi.services.projects import ProjectsService


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