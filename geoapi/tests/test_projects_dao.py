import pytest
from geoapi.services.projects import ProjectsService
from geoapi.services.users import UserService



def test_create_project(users_fixture):
    print("test")
    user = UserService.getUser("test1")
    data = {
        "name": "test name",
        "description": "test description"
    }
    proj = ProjectsService.create(data, user)
    assert proj.id is not None
    assert len(proj.users) == 1
    assert proj.name == "test name"