import pytest
from geoapi.services.projects import ProjectsService
from geoapi.services.users import UserService
from geoapi.models.users import User


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

def test_insert_feature_geojson():
    pass

def test_insert_feature_collection():
    pass

def test_insert_image():
    pass

def test_remove_feature():
    pass

def test_remove_feature_removes_assets():
    pass

