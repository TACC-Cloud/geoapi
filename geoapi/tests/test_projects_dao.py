import pytest
from geoapi.dao.projects import ProjectsDAO
from geoapi.dao.users import UserDAO



def test_create_project(users_fixture):
    print("test")
    user = UserDAO.getUser("test1")
    data = {
        "name": "test name",
        "description": "test description"
    }
    proj = ProjectsDAO.create(data, user)
    assert proj.id is not None
    assert len(proj.users) == 1
    assert proj.name == "test name"