import pytest

from geoapi.initdb import initDB
from geoapi.models.users import User
from geoapi.db import db_session
from geoapi.app import app

def pytest_runtest_setup(item):
    initDB()

def pytest_runtest_teardown(item):
    db_session.remove()


@pytest.fixture(scope="function")
def users_fixture():
    u1 = User(username="test1", jwt="testjwt")
    u2 = User(username="test2", jwt="testjwt")
    db_session.add_all([u1, u2])
    db_session.commit()
    users = db_session.query(User).all()
    print("**********************************")
    print(users)


@pytest.fixture
def client():
    client = app.test_client()
    yield client
