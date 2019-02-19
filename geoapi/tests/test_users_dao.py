import pytest
from geoapi.dao.users import UserDAO
from geoapi.dao.projects import ProjectsDAO


def test_user_get(users_fixture):
    user = UserDAO.getUser("test1")
    assert user.id is not None
    assert user.created is not None


def test_user_create(users_fixture):
    user = UserDAO.create("newUser")
    assert user.id is not None
    assert user.created is not None
    assert user.username == 'newUser'

def test_projects_for_user(users_fixture):
    user = UserDAO.getUser("test1")
    data = {
        "name": 'new project',
        'description': 'test'
    }
    ProjectsDAO.create(data, user)
    myProjects = UserDAO.projectsForUser(user.username)
    assert len(myProjects) == 1
    assert myProjects[0].name == 'new project'