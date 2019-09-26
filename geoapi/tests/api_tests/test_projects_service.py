from geoapi.services.projects import ProjectsService
from geoapi.models import User


def test_create_project(dbsession):
    user = dbsession.query(User).get(1)
    data = {
        "name": "test name",
        "description": "test description"
    }
    proj = ProjectsService.create(data, user)
    assert proj.id is not None
    assert len(proj.users) == 1
    assert proj.name == "test name"

